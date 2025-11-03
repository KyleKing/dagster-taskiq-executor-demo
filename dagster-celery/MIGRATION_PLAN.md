# Celery to Taskiq Migration Plan

## Executive Summary

The dagster-celery project is a Dagster integration library that enables distributed job execution using Celery as the task queue. To migrate to taskiq, we need to replace Celery's task submission, result polling, and worker management with equivalent taskiq functionality while maintaining the same Dagster executor and launcher interfaces.

**Scope:** Replace underlying task queue (Celery → taskiq) while keeping Dagster integration layer intact

**Impact:** Library code only - Dagster's API and configuration remain unchanged for end users

## Current Architecture Overview

### Execution Flows

#### Flow 1: Step-Level Execution (via Executor)

```
Job Definition
    ↓
celery_executor (executor_def)
    ↓
CeleryExecutor.execute()
    ↓
core_celery_execution_loop()
    ├─ make_app() → Celery app
    ├─ Submit steps via _submit_task()
    │   ├─ Serialize ExecuteStepArgs
    │   ├─ Call task.si(args).apply_async(queue, priority)
    │   └─ Return AsyncResult
    ├─ Poll results (1s tick)
    │   ├─ Check result.ready()
    │   ├─ Get events via result.get()
    │   └─ Yield DagsterEvent
    └─ Error handling & task revocation
```

#### Flow 2: Run-Level Execution (via RunLauncher)

```
User runs job
    ↓
CeleryRunLauncher.launch_run()
    ├─ Serialize ExecuteRunArgs
    ├─ Create task via create_execute_job_task()
    ├─ Submit task.si(args).apply_async()
    └─ Store task_id in run tags
        ↓
CeleryRunLauncher.check_run_worker_health()
    ├─ Retrieve task_id from run tags
    ├─ Poll task state (ready, state)
    └─ Return health status
```

### Core Components to Replace

| Component | Current | Must Replace | Rationale |
|-----------|---------|--------------|-----------|
| Task definition | `@celery.task` decorator | taskiq task decorator | Queue abstraction |
| Task submission | `task.si().apply_async()` | taskiq broker method | Core functionality |
| Result polling | `AsyncResult.ready()/.get()` | taskiq result backend | Core functionality |
| Task revocation | `result.revoke()` | taskiq equivalent | Graceful shutdown |
| App creation | `Celery()` instance | taskiq broker instance | Configuration |
| Worker process | `celery worker` command | taskiq worker command | Execution |
| Health checks | Task state (SUCCESS/FAILURE) | taskiq state | Monitoring |

## Detailed Migration Tasks

### Phase 1: Foundation (Weeks 1-2)

#### Task 1.1: Create taskiq equivalents module
**File:** `dagster_taskiq/taskiq_app.py`

Replace `make_app()`:
```python
from taskiq import InMemoryBroker, AsyncBroker

def make_broker(broker_url=None, result_backend=None):
    """Create taskiq broker with given configuration."""
    # Parse broker_url (Redis, etc.)
    # Create broker instance
    # Configure result backend
    # Return broker
```

**Considerations:**
- taskiq supports multiple brokers (Redis, RabbitMQ via plugins)
- Result backend configuration differs from Celery
- Task routing handled differently (via task metadata, not queue config)

#### Task 1.2: Task wrapper module
**File:** `dagster_taskiq/task_wrappers.py`

Define taskiq tasks replacing Celery tasks:
```python
@broker.task
async def execute_plan(execute_step_args_packed, executable_dict):
    # Same logic as create_task()
    pass

@broker.task(task_id="execute_job")
async def execute_job(execute_job_args_packed):
    # Same logic as create_execute_job_task()
    pass
```

**Challenges:**
- taskiq supports async/sync - need to maintain sync for Dagster compatibility
- Task naming and routing strategy
- Context/self access (taskiq vs celery.Task.request)

#### Task 1.3: Update executor.py
**Changes:**
- Replace `_submit_task()` to use taskiq instead of Celery
- Update `CeleryExecutor` → `TaskiqExecutor` (or keep name for compatibility)
- Modify `app_args()` to return taskiq-compatible config

**Key Change:**
```python
# OLD (Celery)
task_signature = task.si(args).apply_async(queue=queue, priority=priority)

# NEW (taskiq)
result = broker.kiq(args)  # or equivalent
```

### Phase 2: Core Execution Loop (Weeks 2-3)

#### Task 2.1: Rewrite core_execution_loop.py
**Changes:**
- Replace `make_app()` call with `make_broker()`
- Update `_submit_task()` call to use taskiq submission
- Rewrite result polling logic:
  - Replace `AsyncResult.ready()` with taskiq equivalent
  - Replace `AsyncResult.get()` with taskiq result retrieval
  - Update exception handling (`TaskRevokedError` → taskiq equivalents)

**Result Polling Differences:**
```python
# OLD (Celery)
if result.ready():
    try:
        events = result.get()
    except TaskRevokedError:
        # Handle revocation

# NEW (taskiq)
# taskiq uses different result checking mechanism
# May need async/await or polling library
```

#### Task 2.2: Update task revocation
**Changes:**
- Replace `result.revoke(terminate=True)` with taskiq equivalent
- Update interrupt handling in execution loop

**Research Needed:**
- How does taskiq handle task cancellation?
- Is it broker-dependent (Redis vs RabbitMQ)?

### Phase 3: Run Launcher (Week 3)

#### Task 3.1: Update launcher.py
**Changes:**
- Replace task creation logic with taskiq equivalents
- Update result status checking:
  ```python
  # OLD: result.state in ['SUCCESS', 'FAILURE', 'STARTED']
  # NEW: taskiq equivalent
  ```
- Update health check implementation
- Modify task ID storage/retrieval

**Key Changes:**
```python
# OLD (Celery)
result = task.si(args).apply_async(queue=queue, priority=run_priority)
task_id = result.task_id

# NEW (taskiq)
result = broker.kiq(args)  # or equivalent
task_id = result.task_id  # taskiq result object
```

### Phase 4: CLI & Configuration (Week 4)

#### Task 4.1: Update CLI commands
**File:** `dagster_taskiq/cli.py`

Changes:
- Replace celery worker start command with taskiq equivalent
- Update configuration parsing/validation
- Modify worker naming and startup

**Current Command:**
```bash
dagster-celery worker start -A dagster_celery.app -q queue-name
```

**New Command:**
```bash
dagster-taskiq worker start -A dagster_taskiq.app  # taskiq doesn't use -q same way
```

#### Task 4.2: Configuration module
**Changes:**
- Replace `dagster_celery_config` module generation
- Update defaults in `defaults.py` → `taskiq_defaults.py`
- Maintain backward compatibility in env var names (optional)

### Phase 5: Testing (Week 4-5)

#### Task 5.1: Update test fixtures
**File:** `dagster_taskiq_tests/conftest.py`

Changes:
- Replace RabbitMQ fixture with broker-appropriate fixture
- Update worker startup in `dagster_taskiq_worker` fixture
- Modify task submission in test utilities

**Test Infrastructure:**
- If using Redis: Redis container instead of RabbitMQ
- If using in-memory: No external dependency for basic tests
- Hybrid: In-memory for unit tests, Redis for integration tests

#### Task 5.2: Rewrite test utilities
**File:** `dagster_taskiq_tests/utils.py`

Changes:
- Update `execute_job_on_taskiq()` helper
- Modify result polling in tests
- Update error scenarios

#### Task 5.3: Adapt test cases
**Changes:**
- Verify execution flow tests pass
- Verify priority handling (if taskiq supports it)
- Verify queue routing (if taskiq supports it)
- Verify health checks

### Phase 6: Documentation & Examples (Week 5)

#### Task 6.1: Update example app
**File:** `example/example_code/definitions.py`

Changes:
- Update executor reference: `celery_executor` → `taskiq_executor`
- Update queue tags (if format changes)
- Update docker-compose for taskiq workers

#### Task 6.2: Documentation
- Update README.md
- Update inline docstrings
- Document configuration options
- Document broker selection (Redis, RabbitMQ, etc.)

#### Task 6.3: Migration guide
- Document upgrade path for users
- Highlight breaking changes
- Document new features/benefits

## Technical Challenges & Solutions

### Challenge 1: Async/Await Compatibility
**Problem:** taskiq is async-native, Dagster execution is sync

**Solutions:**
1. Use `asyncio.run()` in sync context
2. Use blocking result access methods if taskiq provides them
3. Create sync wrapper around async tasks

**Recommendation:** Test actual taskiq API for blocking result access

### Challenge 2: Priority & Queue Routing
**Problem:** taskiq's priority/routing model differs from Celery

**Current Celery Model:**
- Explicit queues with routing keys
- Priority per task (0-10)
- Workers subscribe to specific queues

**taskiq Alternatives:**
- Labels/tags for routing
- Priority support depends on broker
- May need custom routing logic

**Solutions:**
1. Evaluate taskiq documentation for native support
2. Implement custom routing if needed
3. Potentially abstract routing layer for future flexibility

### Challenge 3: Task Result Serialization
**Problem:** Complex Dagster objects need serialization

**Current:** Uses Dagster's `pack_value()` / `unpack_value()`

**Taskiq Compatibility:** Research taskiq's serialization strategy
- Does taskiq use json/pickle?
- Can we use Dagster's serialization?
- May need custom serializer

### Challenge 4: Worker Discovery & Health Checks
**Problem:** taskiq may not expose task state like Celery

**Current Celery Model:**
- `AsyncResult.state` returns (PENDING, STARTED, SUCCESS, FAILURE, etc.)
- `result.worker` gives worker information

**taskiq Alternative:**
- May rely purely on result backend
- Worker information might not be available
- May need alternative health check approach

**Solutions:**
1. Use result backend polling only
2. Implement heartbeat mechanism if needed
3. Potentially accept reduced health check capabilities

### Challenge 5: Dynamic Configuration Module
**Problem:** CLI dynamically generates `dagster_celery_config` module

**Current Approach:**
- Writes Python file to disk
- Imports via sys.path manipulation
- Used by workers via `-A` flag

**taskiq Approach:**
- May use environment variables instead
- May use configuration objects
- Need to research taskiq's configuration patterns

## Dependency Changes

### Current
```python
install_requires=[
    "dagster",
    "celery>=4.3.0",
    "click>=5.0,<9.0",
]
```

### Proposed
```python
install_requires=[
    "dagster",
    "taskiq>=0.11.0",  # Research minimum version
    "click>=5.0,<9.0",
]

extras_require={
    "redis": ["taskiq-redis"],      # For Redis broker
    "rabbitmq": ["taskiq-aio-pika"], # For RabbitMQ
    "inmemory": [],                  # Built-in
    "test": ["docker"],
}
```

## Backward Compatibility Strategy

### Public API Preservation
- Keep `celery_executor` export (optional: deprecation warning)
- Keep `CeleryRunLauncher` export (optional: deprecation warning)
- Keep tag constants unchanged
- Keep configuration schema compatible

### User Migrations
- Minimal code changes needed if using public APIs
- Main change: broker configuration format
- Example: `broker: "redis://..."` vs `broker: "pyamqp://..."`

### Deprecation Path (Optional)
```python
# setup.py
warnings.warn(
    "dagster-celery is deprecated, use dagster-taskiq instead",
    DeprecationWarning,
    stacklevel=2
)
```

## Testing Strategy

### Unit Tests
- Mock taskiq broker
- Test executor logic independently
- Test configuration parsing

### Integration Tests
- Real taskiq broker (Redis or in-memory)
- Real Dagster instance
- Real worker processes

### Test Scenarios
1. Single step execution
2. Multi-step job execution
3. Priority ordering
4. Queue routing (if supported)
5. Job interruption/revocation
6. Error handling
7. Health checks
8. Task resumption

### Test Infrastructure
**Option A: In-Memory (Fastest)**
- Use taskiq's InMemoryBroker for quick tests
- No external dependencies
- Trade-off: Doesn't test real async behavior

**Option B: Redis (Most Common)**
- Use Redis container in tests
- Closest to production
- Slightly slower than in-memory

**Option C: Hybrid (Recommended)**
- InMemoryBroker for basic tests
- Redis for integration tests
- Marked with different test markers

## Migration Timeline

```
Week 1:
  - Task 1.1: Create taskiq app module
  - Task 1.2: Task wrapper module
  - Task 1.3: Update executor basic changes

Week 2:
  - Task 2.1: Rewrite execution loop
  - Task 2.2: Task revocation logic

Week 3:
  - Task 3.1: Update launcher
  - Continue execution loop refinement

Week 4:
  - Task 4.1: Update CLI
  - Task 4.2: Configuration module
  - Task 5.1-5.2: Update test infrastructure

Week 5:
  - Task 5.3: Adapt test cases
  - Task 6: Documentation & examples
  - Buffer for debugging/refinement
```

## Success Criteria

1. All existing tests pass with taskiq backend
2. Example application works with taskiq
3. CLI commands work (worker start/stop)
4. Priority/queue routing works (or documented workarounds)
5. Health checks functional
6. Performance comparable to Celery
7. Documentation updated
8. Deprecation path clear (if applicable)

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| taskiq API incompleteness | Medium | High | Early research, proof of concept |
| Result serialization issues | Medium | High | Design custom serializer early |
| Performance regression | Low | Medium | Benchmarking throughout |
| Test infrastructure complexity | Medium | Medium | Start with in-memory broker |
| User migration friction | Low | Medium | Comprehensive docs & examples |

## Resource Requirements

- 1 Senior Engineer (4-5 weeks)
- taskiq documentation review
- Potential community engagement for feedback
- Time for proof-of-concept if uncertainties remain

## Next Steps

1. Review taskiq documentation thoroughly
2. Build minimal proof-of-concept (task submission + polling)
3. Validate all technical challenges have solutions
4. Refine timeline based on POC learnings
5. Begin Phase 1 development

## Questions to Research

1. Does taskiq have async/sync API options?
2. How does result backend work in taskiq?
3. What serialization does taskiq use?
4. Can taskiq access worker information?
5. Does taskiq support task cancellation/revocation?
6. What's the recommended broker for production?
7. How does priority work in taskiq?
8. Can we customize routing in taskiq?
9. What's the task state model (similar to Celery)?
10. Does taskiq have built-in health check mechanisms?

