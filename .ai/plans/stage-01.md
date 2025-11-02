# Stage 01 – TaskIQ Executor Foundation

## Goals
- Implement the Dagster ⇄ TaskIQ executor pipeline so ops can be dispatched through SQS with exactly-once semantics.
- Deliver the execution payload contract that downstream worker and autoscaler stages will consume.

## Current State
- Dagster configuration, jobs, schedules, and tests are in place under `app/src/dagster_taskiq`.
- Settings already expose SQS queue names, AWS endpoints, and Postgres connection details.
- `app/src/dagster_taskiq/taskiq_executor/__init__.py` is a stub; no executor, payload models, or broker wiring exist.
- Pulumi infrastructure provisions FIFO queues (`deploy/modules/taskiq.py`) but nothing is publishing messages yet.

## Tasks
1. **Define execution payloads and idempotency helpers**
   - Introduce dataclasses (see design spec for `OpExecutionTask`, `ExecutionResult`, `IdempotencyRecord`) in a new module such as `task_payloads.py`.
   - Encode payloads using JSON (keep ASCII) and ensure all fields are serialisable without custom pickling.
   - Compute idempotency keys as `{run_id}:{step_key}` and persist state using Dagster's event log storage or a dedicated Postgres table via SQLAlchemy.
   - Provide utilities to mark tasks `PENDING → RUNNING → COMPLETED/FAILED` with retry-safe transitions.

2. **Wrap TaskIQ's SQS broker for LocalStack**
   - Create a thin wrapper (e.g., `LocalStackSqsBroker(settings: Settings)`) around `taskiq_aio_sqs.SqsAsyncBroker`.
   - Configure queue URL, region, visibility timeout, deduplication scope, and DLQ from `settings`.
   - Implement exponential backoff (jittered) for broker startup and reconnection (per requirement 2.5).
   - Surface structured logging via `structlog`.

3. **Implement `DagsterTaskIQExecutor`**
   - Build an `ExecutorDefinition` that:  
     a. Serialises each executable Dagster step into an `OpExecutionTask`.  
     b. Enqueues the task onto the SQS broker.  
     c. Tracks futures/promises so overall run resolution matches Dagster expectations.  
   - Use Dagster public APIs (`dagster._core` internals should be avoided) by leveraging `execute_job`, `Executor`, and `ExecuteStepPlan`. Mirror the Celery executor pattern linked in the spec.
   - Ensure executor configuration is exposed via `@executor` decorator so repository definitions can select it (update `dagster_taskiq/dagster_jobs/repository.py` to register the executor as the default).

4. **Handle exactly-once and failure recovery**
   - Before dispatching a task, check idempotency storage; skip enqueue if already `COMPLETED`.
   - When a worker reports completion/failure, update the idempotency state accordingly.
   - Implement visibility-timeout handling by re-marking `RUNNING` tasks stuck longer than `settings.taskiq_visibility_timeout`.

5. **Testing and validation scaffolding**
   - Add interface-level tests (focus on `Executor` behaviour) using a lightweight in-memory broker stub that mimics SQS semantics; avoid hitting LocalStack in unit tests.
   - Verify `dagster.yaml` and `DagsterInstance` wiring accept the new executor (may require updating `DagsterPostgreSQLConfig`).
   - Update documentation (`app/TESTING.md`, if needed) to describe executor-focused test strategy.

## Exit Criteria
- `dagster_taskiq.taskiq_executor` exports `DagsterTaskIQExecutor`, payload dataclasses, and a LocalStack-aware broker wrapper.
- Dagster jobs default to the TaskIQ executor through `Definitions` or job-level configuration.
- Idempotency storage layer is defined with clear transitions and tests covering happy path and duplicate task suppression.
- New tests pass locally: `cd app && uv run pytest`.
