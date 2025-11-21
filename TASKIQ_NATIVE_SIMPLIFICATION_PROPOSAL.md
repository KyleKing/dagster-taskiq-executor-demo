# TaskIQ-Native Simplification Proposal

**Date**: 2025-11-20
**Branch**: `claude/taskiq-native-simplification-01DWsr61fJjDwymAkxdcMuFU`
**Goal**: Simplify dagster-taskiq by using more TaskIQ primitives and dropping non-essential features

## Current Implementation Analysis

### Code Complexity Metrics

- **Total Lines**: ~2,433 lines of Python code
- **Modules**: 15 Python files
- **Key Components**:
  - Custom orchestration loop: ~300 lines (`core_execution_loop.py`)
  - Custom broker classes: ~180 lines (`cancellable_broker.py`, `broker.py`)
  - Configuration management: ~200 lines (`make_app.py`, `config.py`, `defaults.py`)
  - Task definitions: ~200 lines (`tasks.py`)
  - Executor/Launcher: ~400 lines (`executor.py`, `launcher.py`)

### Current Architecture Complexity

**Custom Components Built**:
1. ✅ Custom orchestration loop for multi-step coordination
2. ✅ Custom broker extension (`CancellableSQSBroker`)
3. ✅ Custom result polling mechanism
4. ✅ Custom cancellation architecture (separate queue)
5. ✅ Custom configuration mapping (Dagster → TaskIQ)
6. ✅ Manual task registration and execution

**TaskIQ Features Currently Used**:
- ✅ `AsyncBroker` base class
- ✅ `@broker.task` decorator
- ✅ `task.kiq()` for async task submission
- ✅ Result backend (S3)
- ⚠️ Middleware - NOT USED (could potentially use)

---

## Simplification Opportunities

### 1. Use TaskIQ's Middleware for Cross-Cutting Concerns

**Current**: Custom logging, metrics collection scattered throughout code

**Simplified**: Use TaskIQ middleware for observability

```python
# New: middleware/logging.py
class DagsterLoggingMiddleware(TaskiqMiddleware):
    """Log Dagster task execution."""

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        logger.info(f"Executing Dagster step: {message.labels.get('step_key')}")
        return message

    async def post_save(self, message: TaskiqMessage, result: TaskiqResult) -> None:
        if result.is_err:
            logger.error(f"Step failed: {message.labels.get('step_key')}")
        else:
            logger.info(f"Step completed: {message.labels.get('step_key')}")

# Add to broker
broker.add_middlewares(DagsterLoggingMiddleware())
```

**Lines Saved**: ~50-100 lines of scattered logging code

---

### 2. Simplify Result Polling with TaskIQ's Built-in `wait_result()`

**Current**: Custom polling loop in `core_execution_loop.py`

```python
# Current: Manual polling
while not await task_result.is_ready():
    if await _check_task_cancelled(task_id):
        ...
    await asyncio.sleep(TICK_SECONDS)

result_data = await task_result.get_result()
```

**Simplified**: Use TaskIQ's `wait_result()` with timeout

```python
# Simplified: Use TaskIQ's built-in method
try:
    result_data = await task_result.wait_result(
        timeout=job_timeout,
        check_interval=TICK_SECONDS
    )
except asyncio.TimeoutError:
    # Handle timeout/cancellation
    ...
```

**Lines Saved**: ~30-50 lines of polling logic per task

**Trade-off**: Less fine-grained cancellation checking, but simpler code

---

### 3. Drop Multi-Step Orchestration, Use Simple Task Chaining

**Current Problem**: The orchestration loop is the most complex part (300+ lines)

**Dagster Feature**: Coordinating dependent steps in an execution plan

**Simplification Options**:

#### Option A: Drop Dependency Orchestration (Simplest)
- **Change**: Each Dagster op becomes independent task
- **Trade-off**: No step-level parallelism within a single job
- **Impact**: Jobs still work, but slower (sequential execution)

```python
# Current: Complex orchestration of dependent steps
for step in execution_plan.get_steps_to_execute():
    if step.dependencies_ready():
        submit_step(step)

# Simplified: Just execute the whole job as one task
@broker.task
async def execute_job(job_args):
    # Execute entire job in worker
    # Dagster's execute_in_process handles dependencies
    return execute_in_process(job_args)
```

**Lines Saved**: ~250 lines (entire orchestration loop)

#### Option B: Use TaskIQ Pipelines for Chaining (More Features)
- **Library**: `taskiq-pipelines`
- **Change**: Use TaskIQ's pipeline middleware for step chaining
- **Trade-off**: More complex than Option A, but preserves some parallelism

```python
# Install taskiq-pipelines
from taskiq_pipelines import PipelineMiddleware

broker.add_middlewares(PipelineMiddleware())

# Define steps with next_task labels
@broker.task(labels={"next_task": "step_2"})
async def step_1(data):
    result = process_step_1(data)
    return result

@broker.task
async def step_2(data):
    return process_step_2(data)
```

**Lines Saved**: ~150-200 lines (simplified orchestration)

**Recommendation**: Start with **Option A** (simplest), consider Option B if parallelism is critical

---

### 4. Simplify Broker Configuration

**Current**: Complex configuration mapping in `make_app.py` (~200 lines)

**Simplified**: Direct SQS broker creation with minimal config

```python
# Current: Complex config resolution, validation, defaults
def make_app(app_args: dict) -> AsyncBroker:
    # ~200 lines of config resolution
    queue_url = config.get("queue_url", defaults.sqs_queue_url)
    sqs_endpoint = config.get("endpoint_url", defaults.sqs_endpoint_url)
    # ... many more lines ...
    broker_config = SqsBrokerConfig(...)
    return broker_config.create_broker(...)

# Simplified: Direct creation with sensible defaults
def make_app(app_args: dict | None = None) -> AsyncBroker:
    """Create TaskIQ broker for Dagster."""
    config = app_args or {}

    # Use environment variables for most config
    queue_url = config.get("queue_url") or os.getenv("DAGSTER_SQS_QUEUE_URL")
    endpoint_url = config.get("endpoint_url") or os.getenv("AWS_ENDPOINT_URL")
    region = config.get("region_name", "us-east-1")

    # Simple S3 backend
    s3_bucket = config.get("s3_bucket") or os.getenv("DAGSTER_S3_BUCKET")
    result_backend = S3Backend(
        bucket_name=s3_bucket,
        endpoint_url=endpoint_url,
        region_name=region,
    )

    # Create broker directly
    broker = SQSBroker(
        endpoint_url=endpoint_url,
        sqs_queue_name=_queue_name_from_url(queue_url),
        region_name=region,
    ).with_result_backend(result_backend)

    return broker
```

**Lines Saved**: ~150 lines of config complexity

**Trade-off**: Fewer config options, rely more on environment variables

---

### 5. Drop Cancellation Feature (Optional Simplification)

**Current**: Separate cancellation queue, custom broker, ~180 lines of code

**Dagster Feature**: Ability to cancel running jobs

**Usage Frequency**: Relatively rare in production

**Simplification**: Remove cancellation support entirely

```python
# Delete files:
# - cancellable_broker.py (~180 lines)
# - cancellable_receiver.py (~100 lines)
# - CANCELLATION.md (documentation burden)

# Simplify launcher.py
async def terminate(self, run_id: str) -> bool:
    """Termination not supported in simplified version."""
    logger.warning("Task cancellation not supported in this executor")
    return False
```

**Lines Saved**: ~280 lines

**Trade-off**: Can't cancel running jobs (must wait for completion or kill workers)

**Recommendation**: Consider if cancellation is worth the complexity for your use case

---

### 6. Use TaskIQ's Task Registry Instead of Manual Registration

**Current**: Manual task creation in `tasks.py`

```python
# Current: Manual task function creation
def create_task(broker: AsyncBroker, **task_kwargs):
    @broker.task(task_name=TASK_EXECUTE_PLAN_NAME, **task_kwargs)
    def _execute_plan(execute_step_args_packed, executable_dict):
        # Task logic
        ...
    return _execute_plan

# Must be called explicitly
execute_plan_task = create_task(broker)
```

**Simplified**: Direct task registration

```python
# Simplified: Direct registration on broker creation
@broker.task(name="dagster_execute_job")
async def execute_job(job_args_packed):
    """Execute a Dagster job."""
    args = unpack_value(job_args_packed, ExecuteRunArgs)
    with DagsterInstance.get() as instance:
        return execute_in_process(
            job=args.job,
            instance=instance,
            run_config=args.run_config,
        )
```

**Lines Saved**: ~50 lines of factory code

**Benefit**: Simpler, more idiomatic TaskIQ code

---

### 7. Drop Health Checks (Optional)

**Current**: Custom health check implementation

**Usage**: Dagster UI shows worker health

**Simplification**: Remove health check support

```python
# launcher.py - simplify
def check_run_worker_health(self, run: DagsterRun) -> WorkerStatus:
    """Health checks not supported."""
    return WorkerStatus.UNKNOWN

# Update capability
supports_check_run_worker_health = False
```

**Lines Saved**: ~30-50 lines

**Trade-off**: Dagster UI can't show worker health status

---

## Proposed Simplified Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Dagster Instance                        │
│                                                             │
│  ┌────────────────┐                                        │
│  │ TaskiqExecutor │  Submits jobs                          │
│  └───────┬────────┘                                        │
│          │                                                  │
└──────────┼──────────────────────────────────────────────────┘
           │
           │ execute_job.kiq(job_args)
           ▼
    ┌─────────────┐
    │ SQS Queue   │
    └──────┬──────┘
           │
           │ poll
           ▼
    ┌─────────────────────────────────────┐
    │      TaskIQ Workers                 │
    │                                     │
    │  execute_job(job_args):             │
    │    └─► execute_in_process()         │
    │        └─► Returns events           │
    │                                     │
    │  Middleware:                        │
    │    - Logging                        │
    │    - Metrics                        │
    └──────────┬──────────────────────────┘
               │
               │ Results
               ▼
        ┌──────────────┐
        │  S3 Backend  │
        └──────────────┘
```

### Simplified Component List

**Keep**:
- ✅ `executor.py` - Dagster executor (simplified)
- ✅ `launcher.py` - Dagster launcher (simplified)
- ✅ `broker.py` - Simple broker config
- ✅ `tasks.py` - Task definitions (simpler)
- ✅ `cli.py` - Worker CLI
- ✅ Middleware (NEW) - Observability

**Remove**:
- ❌ `core_execution_loop.py` - No custom orchestration
- ❌ `cancellable_broker.py` - No cancellation
- ❌ `cancellable_receiver.py` - No cancellation
- ❌ `make_app.py` - Simplified to 30 lines
- ❌ `config.py` - Merge into broker.py
- ❌ `defaults.py` - Use env vars directly

**Lines Reduced**: From ~2,433 to ~1,000 lines (~60% reduction)

---

## Implementation Plan

### Phase 1: Core Simplifications (High Value)

1. **Simplify `make_app.py`** - Remove config complexity
   - Direct broker creation
   - Environment variable-based config
   - **Effort**: 2 hours
   - **Lines saved**: ~150

2. **Replace orchestration loop with simple job execution**
   - Remove `core_execution_loop.py`
   - Jobs execute as single tasks
   - **Effort**: 3 hours
   - **Lines saved**: ~300

3. **Add TaskIQ middleware for logging**
   - Create `middleware/logging.py`
   - Replace scattered logging
   - **Effort**: 1 hour
   - **Lines saved**: ~50

### Phase 2: Feature Removals (Optional)

4. **Remove cancellation support** (if acceptable)
   - Delete cancellation files
   - Update launcher
   - **Effort**: 1 hour
   - **Lines saved**: ~280

5. **Simplify health checks** (if acceptable)
   - Remove custom implementation
   - Return UNKNOWN
   - **Effort**: 30 minutes
   - **Lines saved**: ~50

### Phase 3: Polish

6. **Update documentation**
   - Rewrite README with simpler API
   - Update examples
   - Document trade-offs
   - **Effort**: 2 hours

**Total Effort**: 8-10 hours for full simplification

---

## Trade-offs Analysis

### What You Gain

✅ **Simpler codebase**: ~60% fewer lines
✅ **More maintainable**: Uses TaskIQ idiomatically
✅ **Easier to understand**: Less custom code
✅ **Better TaskIQ integration**: Uses middleware, native features
✅ **Faster onboarding**: Fewer concepts to learn

### What You Lose

❌ **Step-level parallelism**: Jobs execute sequentially (slower)
❌ **Cancellation**: Can't stop running jobs
❌ **Health checks**: Can't see worker status in UI
❌ **Fine-grained config**: Fewer config options
❌ **Dagster-Celery parity**: Not a drop-in replacement

### Acceptable Use Cases

**Good Fit**:
- ✅ Small to medium Dagster jobs (few ops)
- ✅ Jobs where wall-clock time isn't critical
- ✅ Development/testing environments
- ✅ Learning TaskIQ integration patterns

**Poor Fit**:
- ❌ Large jobs with many parallel steps
- ❌ Production systems requiring cancellation
- ❌ Migration from dagster-celery (feature gaps)
- ❌ Jobs with strict SLAs

---

## Alternative: Hybrid Approach

Instead of removing features entirely, make them **optional**:

```python
# executor.py - with feature flags
TASKIQ_CONFIG = {
    "queue_url": Field(...),
    "enable_orchestration": Field(
        bool,
        default_value=False,
        description="Enable step-level orchestration (slower startup, faster execution)"
    ),
    "enable_cancellation": Field(
        bool,
        default_value=False,
        description="Enable task cancellation (requires separate cancel queue)"
    ),
    "execution_mode": Field(
        str,
        default_value="simple",
        description="'simple' (one task per job) or 'orchestrated' (step-level parallelism)"
    ),
}

# Executor chooses implementation
if config["execution_mode"] == "simple":
    return SimpleTaskiqExecutor(...)  # New, simplified version
else:
    return OrchestatedTaskiqExecutor(...)  # Current complex version
```

**Benefits**:
- ✅ Users choose complexity vs simplicity
- ✅ Can migrate gradually
- ✅ Preserves features for those who need them

**Costs**:
- ❌ More code to maintain (two implementations)
- ❌ More testing complexity
- ❌ Documentation overhead

---

## Recommendation

### Recommended Approach: Simplified Default with Optional Features

**Tier 1: Core (Always Included)**
- ✅ Simple job execution (whole job as one task)
- ✅ S3 result backend
- ✅ Basic logging middleware
- ✅ Environment-based configuration

**Tier 2: Optional (Feature Flags)**
- 🔧 Step-level orchestration (`enable_orchestration=true`)
- 🔧 Cancellation (`enable_cancellation=true`)

**Tier 3: Removed**
- ❌ Health checks (too complex for value)
- ❌ Multi-queue routing (already removed)
- ❌ Priority scheduling (already removed)

### Next Steps

1. **Implement simple version** (Phases 1-2)
2. **Test with real Dagster jobs**
3. **Measure performance impact** (simple vs orchestrated)
4. **Decide on hybrid approach** based on results
5. **Update documentation** with clear trade-offs

---

## Code Examples: Before vs After

### Example 1: Broker Creation

**Before** (200 lines):
```python
def make_app(app_args: dict | None = None) -> AsyncBroker:
    config = app_args or {}
    queue_url = config.get("queue_url", defaults.sqs_queue_url)
    sqs_endpoint = config.get("endpoint_url", defaults.sqs_endpoint_url)
    region_name = config.get("region_name", defaults.aws_region_name)
    source_overrides = _dict_from_source(config.get("config_source"))
    # ... 180 more lines ...
    return broker_config.create_broker(result_backend=result_backend)
```

**After** (30 lines):
```python
def make_app(app_args: dict | None = None) -> AsyncBroker:
    """Create simple TaskIQ broker for Dagster."""
    config = app_args or {}

    # Simple config from env vars
    broker = SQSBroker(
        endpoint_url=config.get("endpoint_url", os.getenv("AWS_ENDPOINT_URL")),
        sqs_queue_name=_parse_queue_name(config.get("queue_url")),
        region_name=config.get("region_name", "us-east-1"),
    )

    # S3 result backend
    backend = S3Backend(
        bucket_name=config.get("s3_bucket", os.getenv("DAGSTER_S3_BUCKET")),
        endpoint_url=config.get("endpoint_url"),
    )

    return broker.with_result_backend(backend)
```

### Example 2: Task Execution

**Before** (300+ lines of orchestration):
```python
async def core_taskiq_execution_loop(...):
    step_results = {}

    while not active_execution.is_complete:
        # Submit ready steps
        for step in active_execution.get_steps_to_execute():
            result = await submit_step(step)
            step_results[step.key] = result

        # Poll for results
        for key, data in step_results.items():
            if await data['result'].is_ready():
                # Process result...
                # Mark dependencies ready...

        await asyncio.sleep(TICK_SECONDS)
```

**After** (20 lines):
```python
@broker.task(name="dagster_execute_job")
async def execute_job(job_args_packed):
    """Execute entire Dagster job in worker."""
    args = unpack_value(job_args_packed, ExecuteRunArgs)

    with DagsterInstance.get() as instance:
        # Dagster handles orchestration internally
        result = execute_in_process(
            job=args.job,
            instance=instance,
            run_config=args.run_config,
        )
        return serialize_value(result)
```

---

## Success Metrics

How to measure if simplification is successful:

1. **Code Metrics**
   - ✅ Target: <1,000 lines of Python (vs 2,433)
   - ✅ Target: <8 Python modules (vs 15)

2. **Performance**
   - ⚠️ Expect: 20-50% slower for jobs with many parallel steps
   - ✅ Same performance for sequential jobs

3. **Maintainability**
   - ✅ New contributors can understand code in <1 hour
   - ✅ Bugs reduced by 40% (fewer edge cases)

4. **Feature Completeness**
   - ✅ 80% of use cases work perfectly
   - ⚠️ 20% of use cases need full orchestration

---

## Conclusion

The current implementation is **comprehensive but complex**. By using more TaskIQ primitives and dropping non-essential features, we can create a **simpler, more maintainable** executor that handles 80% of use cases with 40% of the code.

**Recommended Strategy**: Implement the simplified version first, then add orchestration/cancellation as **optional features** if specific use cases demand them.

This "progressive enhancement" approach provides:
- ✅ Simple default for most users
- ✅ Advanced features for those who need them
- ✅ Clear documentation of trade-offs
- ✅ Easier maintenance and testing
