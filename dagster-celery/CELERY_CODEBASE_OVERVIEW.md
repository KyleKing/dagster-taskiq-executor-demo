# Dagster-Celery Codebase Overview

## Project Structure

```
dagster-celery/
├── dagster_celery/              # Main package
│   ├── __init__.py              # Exports celery_executor
│   ├── version.py               # Version management
│   ├── executor.py              # Core CeleryExecutor implementation
│   ├── tasks.py                 # Task definitions (execute_plan, execute_job, resume_job)
│   ├── config.py                # Configuration constants and dict_wrapper
│   ├── defaults.py              # Default settings
│   ├── app.py                   # Celery app initialization
│   ├── make_app.py              # App factory with task routing
│   ├── core_execution_loop.py   # Main execution orchestration
│   ├── launcher.py              # CeleryRunLauncher for run execution
│   ├── cli.py                   # CLI commands for worker management
│   └── tags.py                  # Tag definitions for priority/queue/task_id
├── dagster_celery_tests/        # Test suite
│   ├── conftest.py              # Pytest fixtures (rabbitmq, instance, worker)
│   ├── utils.py                 # Test utilities and execution helpers
│   ├── repo.py                  # Test repository with sample jobs
│   ├── test_execute.py          # Core execution tests
│   ├── test_priority.py         # Priority handling tests
│   ├── test_queues.py           # Queue routing tests
│   ├── test_launcher.py         # Run launcher tests
│   ├── test_cli.py              # CLI tests
│   └── ...                      # Other test modules
├── example/                     # Example application
│   ├── pyproject.toml           # Poetry configuration
│   ├── docker-compose.yaml      # Full stack compose (Postgres, Redis, Celery workers, Flower)
│   ├── Dockerfile               # Docker image for example
│   └── example_code/
│       └── definitions.py       # Sample job definitions
├── docker-compose.yaml          # Development RabbitMQ container
├── setup.py                     # Package setup
├── setup.cfg                    # Package metadata
├── tox.ini                      # Testing configuration
└── conftest.py                  # Root pytest configuration

```

## Core Components

### 1. Executor (`dagster_celery/executor.py`)

**Main Entry Point:** `celery_executor` function/decorator

**Key Classes:**
- `CeleryExecutor`: Main executor class implementing Dagster's `Executor` interface
  - Manages broker, backend, and Celery app configuration
  - Routes execution to `core_celery_execution_loop`
  - Supports retry mode configuration

**Configuration Schema (CELERY_CONFIG):**
```python
{
    "broker": StringSource (optional, default: pyamqp://guest@localhost//)
    "backend": StringSource (optional, default: rpc://)
    "include": List[str] (optional modules to import in workers)
    "config_source": Permissive dict (additional Celery settings)
    "retries": RetryMode configuration
}
```

**Key Methods:**
- `execute()` - Orchestrates job execution using `core_celery_execution_loop`
- `for_cli()` - Creates executor instance for CLI operations
- `app_args()` - Returns configuration for app factory

### 2. Core Execution Loop (`dagster_celery/core_execution_loop.py`)

**Main Function:** `core_celery_execution_loop(job_context, execution_plan, step_execution_fn)`

**Responsibilities:**
- Creates Celery app with `make_app()`
- Manages step execution submission and monitoring
- Handles task result polling and event processing
- Manages interrupts and task revocation
- Applies step/run priority tags
- Enforces artifact persistence requirement (no in-memory IO managers)

**Key Features:**
- **Priority System:**
  - Run-level priority: `DAGSTER_CELERY_RUN_PRIORITY_TAG` 
  - Step-level priority: `DAGSTER_CELERY_STEP_PRIORITY_TAG`
  - Combined priority = run_priority + step_priority
  
- **Queue Routing:**
  - Uses `DAGSTER_CELERY_QUEUE_TAG` to select queue
  - Default queue: "dagster"
  - Supports multiple queues for different step types
  
- **Task Submission:**
  - Calls `step_execution_fn` (typically `_submit_task`)
  - Returns Celery `AsyncResult` for polling
  
- **Result Polling:**
  - 1-second tick interval (TICK_SECONDS)
  - Deserializes step events from task results
  - Revokes tasks on interruption
  
- **Error Handling:**
  - Catches `TaskRevokedError` and subprocess exceptions
  - Yields DagsterEvents for monitoring
  - Raises `DagsterSubprocessError` on worker failures

### 3. Task Definitions (`dagster_celery/tasks.py`)

**Three Main Tasks:**

1. **`create_task(celery_app)` -> `execute_plan` task**
   - Executes individual steps within a job
   - Unpacks serialized `ExecuteStepArgs`
   - Loads run, job, and execution plan from instance
   - Reports engine events with worker hostname
   - Returns serialized list of `DagsterEvent` objects
   - Signature: `.si(execute_step_args_packed, executable_dict)`

2. **`create_execute_job_task(celery_app)` -> `execute_job` task**
   - Full job execution (used by CeleryRunLauncher)
   - Calls Dagster's `_execute_run_command_body`
   - Handles job-level setup/teardown
   - Returns exit code
   - Config: `track_started=True`
   - Signature: `.si(execute_job_args_packed)`

3. **`create_resume_job_task(celery_app)` -> `resume_job` task**
   - Resumes interrupted/failed jobs
   - Calls `_resume_run_command_body`
   - Signature: `.si(resume_job_args_packed)`

**Task Payload Serialization:**
- Uses Dagster's `pack_value()` / `unpack_value()` for serialization
- Packed types: `ExecuteStepArgs`, `ExecuteRunArgs`, `ResumeRunArgs`

### 4. Celery App Configuration (`dagster_celery/make_app.py`)

**`make_app(app_args=None)`**
- Factory function that creates configured Celery app
- Imports defaults from `dagster_celery.defaults` module
- Optionally imports user config from `dagster_celery_config` module
- Configures task queues and routing

**Queue Configuration:**
```python
Queue("dagster", routing_key="dagster.#", queue_arguments={"x-max-priority": 10})
```

**Task Routes:**
```python
{
    "execute_plan": {"queue": "dagster", "routing_key": "dagster.execute_plan"},
    "execute_job": {"queue": "dagster", "routing_key": "dagster.execute_job"},
    "resume_job": {"queue": "dagster", "routing_key": "dagster.resume_job"},
}
```

**Priority Configuration:**
- Max priority: 10
- Default priority: 5
- Worker prefetch multiplier: 1 (process one task at a time)

### 5. Run Launcher (`dagster_celery/launcher.py`)

**Class:** `CeleryRunLauncher(RunLauncher, ConfigurableClass)`

**Purpose:** Launches full job runs (as opposed to individual steps via executor)

**Key Methods:**
- `launch_run()` - Submits job as Celery task via `execute_job` task
- `resume_run()` - Resumes interrupted runs
- `terminate()` - Revokes running Celery task
- `check_run_worker_health()` - Polls task state (SUCCESS, FAILURE, STARTED, UNKNOWN)
- `get_run_worker_debug_info()` - Returns task status and worker info

**Configuration Schema:**
- `broker`, `backend`, `include`, `config_source`, `default_queue`

**Run Tagging:**
- Stores Celery task ID in `DAGSTER_CELERY_TASK_ID_TAG`
- Enables health checks and termination via task ID lookup

### 6. CLI (`dagster_celery/cli.py`)

**Main Command:** `dagster-celery` CLI

**Key Subcommands:**
- `worker start` - Start a Celery worker
  - Configuration from YAML (dagster.yaml)
  - Custom worker naming
  - Task module discovery via `dagster_celery_config`
  
- `worker terminate` - Gracefully shutdown worker
- `worker list` - List active workers

**Configuration Handling:**
- Reads from `execution.config` or `execution.celery` (legacy) in YAML
- Validates against `celery_executor.config_schema`
- Generates dynamic `dagster_celery_config` module in instance directory

**Worker Configuration:**
```bash
dagster-celery worker start -y /path/to/dagster.yaml -A dagster_celery.app -q queue-name
```

### 7. Default Configuration (`dagster_celery/defaults.py`)

```python
broker_url = "pyamqp://guest@{DAGSTER_CELERY_BROKER_HOST:localhost}:5672//"
result_backend = "rpc://"
task_default_priority = 5
task_default_queue = "dagster"
worker_prefetch_multiplier = 4 (note: DEFAULT_CONFIG sets to 1)

broker_transport_options = {
    "max_retries": 3,
    "interval_start": 0,
    "interval_step": 0.2,
    "interval_max": 0.5,
}
```

### 8. Tags (`dagster_celery/tags.py`)

**Tag Constants:**
```python
DAGSTER_CELERY_STEP_PRIORITY_TAG = "dagster-celery/priority"       # Step priority
DAGSTER_CELERY_RUN_PRIORITY_TAG = "dagster-celery/run_priority"   # Run priority
DAGSTER_CELERY_QUEUE_TAG = "dagster-celery/queue"                 # Queue selection
DAGSTER_CELERY_TASK_ID_TAG = "dagster-celery/task_id"             # Task ID tracking
```

**Usage in Job Definition:**
```python
@job(
    executor_def=celery_executor,
    tags={
        "dagster-celery/queue": "short-queue",      # Route to specific queue
        "dagster-celery/run_priority": "10",        # Run-level priority
    }
)
def my_job():
    pass
```

## Testing Setup

### Test Infrastructure

**Fixtures (`dagster_celery_tests/conftest.py`):**
- `rabbitmq` - Session-scoped RabbitMQ container (docker-compose)
- `instance` - Function-scoped DagsterInstance with temp directory
- `dagster_celery_worker` - Function-scoped Celery worker subprocess
- `tempdir` - Temporary directory for test IO

**Test Utilities (`dagster_celery_tests/utils.py`):**
- `execute_job_on_celery()` - Context manager for job execution
- `execute_eagerly_on_celery()` - Eager execution via Celery (task_always_eager)
- `start_celery_worker()` - Start worker subprocess
- Event filtering helpers

**Test Repository (`dagster_celery_tests/repo.py`):**
- Simple job: `test_job` - single op
- Serial job: `test_serial_job` - sequential ops
- Diamond job: `test_diamond_job` - parallel with merge
- Test repo decorated with `@repository`

### Test Execution

**Command:** `pytest` via tox
```bash
tox                          # Run full test suite
pytest dagster_celery_tests/ # Run specific tests
```

**Test Coverage:**
- `test_execute.py` - Step execution, job execution, event serialization
- `test_priority.py` - Priority ordering and scheduling
- `test_queues.py` - Queue routing and selection
- `test_launcher.py` - Run launcher functionality
- `test_cli.py` - CLI commands
- `test_config.py` - Configuration validation
- `test_utils.py` - Utility functions

**Test Dependencies (tox.ini):**
- `dagster[test]`
- `dagster-postgres`
- `dagster-k8s`
- `dagster-aws`
- `dagster-pandas`
- `dagster-gcp`
- Docker (for containers)

## Dependencies

### Core Dependencies (setup.py)

```python
install_requires=[
    "dagster",              # Orchestration framework
    "celery>=4.3.0",        # Task queue
    "click>=5.0,<9.0",      # CLI framework
]

extras_require={
    "flower": ["flower"],        # Celery monitoring
    "redis": ["redis"],          # Redis broker/backend
    "kubernetes": ["kubernetes"], # K8s deployment
    "test": ["docker"],          # Test infrastructure
}
```

### Example App Dependencies (example/pyproject.toml)

```toml
[tool.poetry.dependencies]
python = ">=3.10,<3.14"
dagster = "^1.7.10"
dagster-postgres = "^0.23.10"
celery = {extras = ["redis"], version = "^5.4.0"}
dagster-webserver = "^1.7.10"
```

## Deployment & Docker

### Example Stack (example/docker-compose.yaml)

**Services:**
1. **PostgreSQL** - Dagster metadata store
2. **Redis** - Celery broker & result backend
3. **Code Location** - Dagster repository (codelocation)
4. **Workers** - Two Celery workers (short-queue, long-queue)
5. **Dagster Daemon** - Job scheduler and monitoring
6. **Dagster Webserver** - Web UI
7. **Flower** - Celery monitoring dashboard (port 5555)

**Worker Configuration:**
```yaml
command: dagster-celery worker start -y /app/celery.yaml -A dagster_celery.app -q short-queue
```

### Docker Image (example/Dockerfile)

```dockerfile
FROM python:3.11-slim
# Install via Poetry
# Copy dagster-celery package and install
# Copy example code
# Expose 3030 (gRPC server)
# CMD: dagster api grpc --port 3030
```

## Key Architectural Patterns

### 1. Serialization Strategy
- Uses Dagster's `pack_value()` / `unpack_value()` for all data
- Preserves complex types through serialization
- Supports distributed execution across workers

### 2. Step vs. Run Execution
- **Executor Mode:** Steps executed individually, orchestration at Dagster level
  - Each step is separate task
  - Supports fine-grained priority and queue routing
  - Higher overhead but better control
  
- **Launcher Mode:** Full job run as single task
  - Job executes completely in single worker
  - Less network overhead
  - Better for jobs that must execute together

### 3. Result Storage
- Default: RPC backend (RabbitMQ)
- Options: Redis, database-backed results
- Results must be persisted (distributed execution requirement)

### 4. Queue-Based Routing
- Multiple queues for different workload types
- Workers consume specific queues
- Enable scaling different job types independently

### 5. Priority System
- Combined: run_priority + step_priority
- Supports Celery native priority (max 10)
- Used for fairness and SLA management

### 6. Health Monitoring
- `CeleryRunLauncher` polls task state
- Tracks task ID in run tags
- Supports health checks and worker status

## Critical Requirements & Constraints

### 1. Persistent Artifact Storage
**Critical Constraint:** Cannot use in-memory IO managers
- Enforced: `execution_plan.artifacts_persisted` check
- Required: filesystem (NFS/S3/GCS) storage
- Reason: Workers are distributed, need shared storage

### 2. Celery Broker Connectivity
- All workers must connect to same broker
- Broker URL must match executor configuration
- Environment: `DAGSTER_CELERY_BROKER_HOST`

### 3. Worker Module Discovery
- Workers discover tasks via `dagster_celery.app` module
- Or custom module specified via `-A` flag
- Must be importable in worker Python environment

### 4. Dynamic Config Module
- CLI generates `dagster_celery_config` module dynamically
- Located in `{DAGSTER_HOME}/dagster_celery/config/{uuid}/`
- Contains broker_url, result_backend, custom settings

## Extension Points for Migration

### 1. Task Submission (`_submit_task`)
- Currently: Calls `apply_async()` on Celery task
- Migration: Would call taskiq broker instead

### 2. Result Polling
- Currently: Polls `AsyncResult.ready()` and `AsyncResult.get()`
- Migration: Would poll taskiq result backend

### 3. Task Revocation
- Currently: `result.revoke(terminate=True)`
- Migration: Equivalent in taskiq

### 4. App Configuration
- Currently: `make_app()` creates Celery instance
- Migration: Would create taskiq broker instance

### 5. CLI Worker Management
- Currently: Launches celery worker processes
- Migration: Would launch taskiq worker processes

## File Paths Summary

| Purpose | Path |
|---------|------|
| Main executor | `/dagster_celery/executor.py` |
| Core orchestration | `/dagster_celery/core_execution_loop.py` |
| Task definitions | `/dagster_celery/tasks.py` |
| App factory | `/dagster_celery/make_app.py` |
| Run launcher | `/dagster_celery/launcher.py` |
| CLI commands | `/dagster_celery/cli.py` |
| Default config | `/dagster_celery/defaults.py` |
| Tag constants | `/dagster_celery/tags.py` |
| Test fixtures | `/dagster_celery_tests/conftest.py` |
| Test utilities | `/dagster_celery_tests/utils.py` |
| Example app | `/example/example_code/definitions.py` |
| Example stack | `/example/docker-compose.yaml` |

