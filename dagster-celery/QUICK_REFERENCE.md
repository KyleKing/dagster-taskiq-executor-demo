# Dagster-Celery Quick Reference

## Key Files & Their Responsibilities

### Executor Layer (Job Execution)
```
dagster_celery/executor.py
├─ @executor("celery") → celery_executor
├─ CeleryExecutor class
│  ├─ __init__() - Stores broker, backend, config, retries
│  ├─ execute() - Routes to core_celery_execution_loop()
│  ├─ app_args() - Returns config dict for make_app()
│  └─ for_cli() - Factory for CLI mode
└─ _submit_task() - Submits individual step to Celery
   ├─ Serializes ExecuteStepArgs with pack_value()
   ├─ Calls task.si().apply_async(queue, priority)
   └─ Returns AsyncResult for polling
```

### Execution Loop (Orchestration)
```
dagster_celery/core_execution_loop.py
└─ core_celery_execution_loop()
   ├─ Creates Celery app via make_app()
   ├─ Validates artifact persistence (CRITICAL)
   ├─ Main loop:
   │  ├─ get_steps_to_execute() - From execution plan
   │  ├─ _submit_task() - Submit to Celery
   │  ├─ Poll results (1s tick)
   │  │  ├─ result.ready() - Check if done
   │  │  ├─ result.get() - Get serialized events
   │  │  └─ Deserialize DagsterEvent
   │  ├─ handle_event() - Update execution state
   │  └─ Yield DagsterEvent for logging
   └─ Cleanup: revoke tasks on interrupt
```

### Task Definitions (Worker Side)
```
dagster_celery/tasks.py
├─ create_task(celery_app)
│  └─ @celery_app.task("execute_plan")
│     ├─ Unpack ExecuteStepArgs
│     ├─ Load run, job, execution plan
│     ├─ execute_plan_iterator() from Dagster
│     ├─ Serialize DagsterEvents
│     └─ Return list[DagsterEvent]
├─ create_execute_job_task(celery_app)
│  └─ @celery_app.task("execute_job")
│     ├─ Unpack ExecuteRunArgs
│     ├─ Call _execute_run_command_body()
│     └─ Return exit code
└─ create_resume_job_task(celery_app)
   └─ @celery_app.task("resume_job")
      ├─ Unpack ResumeRunArgs
      └─ Call _resume_run_command_body()
```

### App Factory (Configuration)
```
dagster_celery/make_app.py
└─ make_app(app_args=None)
   ├─ Create Celery("dagster")
   ├─ Load defaults from dagster_celery.defaults
   ├─ Optionally load dagster_celery_config (user settings)
   ├─ Configure task queues
   │  └─ Queue("dagster", routing_key="dagster.#", max-priority=10)
   ├─ Configure task routes
   │  ├─ execute_plan → dagster queue
   │  ├─ execute_job → dagster queue
   │  └─ resume_job → dagster queue
   └─ Return configured Celery app
```

### Run Launcher (Full Job Execution)
```
dagster_celery/launcher.py
└─ CeleryRunLauncher(RunLauncher, ConfigurableClass)
   ├─ launch_run()
   │  ├─ Serialize ExecuteRunArgs
   │  ├─ Submit via execute_job task
   │  ├─ Store task_id in run tags
   │  └─ Report engine event
   ├─ terminate()
   │  ├─ Retrieve task_id from run tags
   │  └─ result.revoke(terminate=True)
   ├─ check_run_worker_health()
   │  ├─ Get result from task_id
   │  ├─ Poll result.state
   │  └─ Return WorkerStatus
   └─ resume_run()
      └─ Similar to launch_run() but for resume
```

### CLI (Worker Management)
```
dagster_celery/cli.py
├─ worker start
│  ├─ Validate config from YAML
│  ├─ Generate dagster_celery_config module
│  ├─ Launch: celery worker -A dagster_celery.app -q queue-name
│  └─ Block or detach based on flags
├─ worker terminate
│  └─ Send SIGTERM to worker process
└─ worker list
   └─ Query Celery for active workers
```

### Configuration
```
dagster_celery/config.py
├─ DEFAULT_CONFIG = {
│  ├─ worker_prefetch_multiplier: 1
│  ├─ broker_transport_options: {...max_retries, intervals...}
│  ├─ task_default_priority: 5
│  └─ task_default_queue: "dagster"
├─ TASK_EXECUTE_PLAN_NAME = "execute_plan"
├─ TASK_EXECUTE_JOB_NAME = "execute_job"
├─ TASK_RESUME_JOB_NAME = "resume_job"
└─ dict_wrapper class (convert dict['key'] → dict.key)

dagster_celery/defaults.py
├─ broker_url = "pyamqp://guest@localhost:5672//"
├─ result_backend = "rpc://"
├─ task_default_priority = 5
├─ task_default_queue = "dagster"
└─ broker_transport_options = {...}

dagster_celery/tags.py
├─ DAGSTER_CELERY_STEP_PRIORITY_TAG = "dagster-celery/priority"
├─ DAGSTER_CELERY_RUN_PRIORITY_TAG = "dagster-celery/run_priority"
├─ DAGSTER_CELERY_QUEUE_TAG = "dagster-celery/queue"
└─ DAGSTER_CELERY_TASK_ID_TAG = "dagster-celery/task_id"
```

## Execution Flow Diagrams

### Step-Level Execution (Executor Mode)

```
User submits job with executor_def=celery_executor
        ↓
Dagster creates execution plan (steps)
        ↓
CeleryExecutor.execute(plan_context, execution_plan)
        ↓
core_celery_execution_loop():
    for each step in execution_plan:
        ├─ _submit_task(app, context, step, queue, priority, known_state)
        │  ├─ pack ExecuteStepArgs
        │  ├─ task.si(args).apply_async(queue="X", priority=N)
        │  └─ return AsyncResult
        ├─ Store AsyncResult by step_key
        └─ Loop polling AsyncResult:
            ├─ result.ready() → check if done
            ├─ result.get() → get serialized DagsterEvents
            ├─ deserialize → DagsterEvent
            ├─ yield event → UI/logging
            └─ Every 1 second check again

Worker (celery worker):
    Receives task "execute_plan"
        ├─ unpack ExecuteStepArgs
        ├─ Load run, job, execution plan
        ├─ execute_plan_iterator() from Dagster
        ├─ Yield DagsterEvent objects
        ├─ Serialize events list
        └─ Return serialized events
```

### Run-Level Execution (Launcher Mode)

```
CeleryRunLauncher.launch_run(context):
    ├─ pack ExecuteRunArgs
    ├─ task.si(args).apply_async(queue=default_queue)
    ├─ result.task_id → store in run.tags[TASK_ID_TAG]
    └─ return

Dagster Daemon monitors:
    CeleryRunLauncher.check_run_worker_health(run):
        ├─ task_id = run.tags[TASK_ID_TAG]
        ├─ result = celery.AsyncResult(task_id)
        ├─ result.state → SUCCESS/FAILURE/STARTED/PENDING
        └─ return WorkerStatus

Worker executes:
    execute_job task:
        ├─ unpack ExecuteRunArgs
        ├─ _execute_run_command_body() from Dagster
        ├─ Runs full job (all steps)
        └─ return exit code
```

## Data Serialization

### Serialization Chain
```
Step Arguments (Executor mode):
    ExecuteStepArgs (Python object)
        ↓
    pack_value() → JSON-serializable dict
        ↓
    Celery sends via broker (JSON)
        ↓
    Worker receives JSON dict
        ↓
    unpack_value(..., as_type=ExecuteStepArgs)
        ↓
    ExecuteStepArgs (Python object)

Result (Worker → Orchestrator):
    [DagsterEvent, DagsterEvent, ...]
        ↓
    [serialize_value(event) for event in events]
        ↓
    List of JSON-serializable dicts
        ↓
    Celery returns via result backend
        ↓
    Orchestrator:
        ├─ result.get() → List of dicts
        ├─ deserialize_value(dict, DagsterEvent)
        └─ yield DagsterEvent
```

## Configuration Hierarchy

### YAML Configuration (Runtime)
```yaml
execution:
  config:
    broker: "redis://localhost:6379/0"
    backend: "redis://localhost:6379/1"
    include: ["my_tasks_module"]
    config_source:
      worker_prefetch_multiplier: 1
      task_serializer: "json"
```

### Defaults (Code)
```python
DEFAULT_CONFIG = {
    "worker_prefetch_multiplier": 1,
    "broker_transport_options": {...},
    "task_default_priority": 5,
    "task_default_queue": "dagster",
}
```

### Dynamic Config (Generated at Runtime)
```python
# File: {DAGSTER_HOME}/dagster_celery/config/{uuid}/dagster_celery_config.py
broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/1'
worker_prefetch_multiplier = 1
# ... other settings
```

### Priority System

```
Run-level priority (tag): 10
    ↓
Step-level priority (tag): 5
    ↓
Combined priority = 10 + 5 = 15
    ↓
Celery uses this for queue ordering
```

### Queue Routing

```
Job tags:
    "dagster-celery/queue": "short-queue"
    ↓
Step inherits queue tag
    ↓
_submit_task() uses step.tags[QUEUE_TAG]
    ↓
task.si().apply_async(queue="short-queue")
    ↓
Worker 1 listens: celery worker -q short-queue
Worker 2 listens: celery worker -q long-queue
    ↓
Task routed to appropriate worker
```

## Critical Constraints

### 1. Artifact Persistence (CRITICAL)
```python
if len(execution_plan.step_keys_to_execute) > 0:
    check.invariant(
        execution_plan.artifacts_persisted,
        "Cannot use in-memory storage with Celery, use filesystem (NFS/S3/GCS)"
    )
```
**Why:** Workers are distributed, need shared persistent storage.

### 2. Broker Connectivity
- All workers must connect to **same broker**
- Broker URL must match executor config
- Environment: `DAGSTER_CELERY_BROKER_HOST`

### 3. Module Discovery
- Workers import tasks from: `dagster_celery.app`
- Or custom via `-A module_name` flag
- Must be in worker's Python path

### 4. Result Backend
- Stores task results
- Default: RPC backend (RabbitMQ)
- Better: Redis or database backend for production

## Testing Essentials

### Fixtures
```python
@pytest.fixture(scope="session")
def rabbitmq():
    # Start RabbitMQ container, return after ready

@pytest.fixture(scope="function")
def dagster_celery_worker(rabbitmq, instance):
    # Start Celery worker subprocess, yield, cleanup
```

### Execution Helpers
```python
with execute_job_on_celery("job_name", instance=instance) as result:
    assert result.output_for_node("op_name") == expected_value
    events = events_of_type(result, "STEP_SUCCESS")
```

### Test Jobs (repo.py)
```python
@op
def simple():
    return 1

@op
def add_one(x):
    return x + 1

@job
def test_job():
    simple()

@job
def test_serial_job():
    add_one(simple())
```

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Worker can't find tasks | Module not in PYTHONPATH | Use `-A` to specify module path |
| Results lost after reboot | RPC backend (transient) | Switch to Redis/database backend |
| Priority not working | Wrong tag name | Use `"dagster-celery/priority"` |
| Queue not routing | No workers on queue | Start worker with `-q queue-name` |
| In-memory storage error | Using default IO manager | Use filesystem/S3/GCS storage |
| Broker timeout | Worker busy | Reduce prefetch_multiplier |

## Extension Points for Taskiq Migration

### 1. Broker Creation
**Current:** `make_app()` in `make_app.py`
**Replace:** Create taskiq broker instead

### 2. Task Submission
**Current:** `task.si().apply_async()` in executor
**Replace:** `broker.kiq()` or taskiq equivalent

### 3. Result Polling
**Current:** `result.ready()` and `result.get()` in core_execution_loop
**Replace:** taskiq result backend API

### 4. Task Revocation
**Current:** `result.revoke(terminate=True)` in core_execution_loop
**Replace:** taskiq cancel/revoke equivalent

### 5. CLI Worker
**Current:** `celery worker` subprocess in cli.py
**Replace:** taskiq worker subprocess

### 6. Health Checks
**Current:** `result.state` in launcher.py
**Replace:** taskiq task state API

