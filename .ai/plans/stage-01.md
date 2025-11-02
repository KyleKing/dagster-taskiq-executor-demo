# Stage 01 – TaskIQ Executor Foundation

## Goals
- Implement the Dagster ⇄ TaskIQ executor pipeline so ops can be dispatched through SQS with exactly-once semantics.
- Deliver the execution payload contract that downstream worker and autoscaler stages will consume.

## Current State
- ✅ Dagster configuration, jobs, schedules, and tests are in place under `app/src/dagster_taskiq`.
- ✅ Settings already expose SQS queue names, AWS endpoints, and Postgres connection details.
- ✅ Task payloads (`OpExecutionTask`, `ExecutionResult`, `IdempotencyRecord`) implemented in `task_payloads.py`.
- ✅ Idempotency storage with PostgreSQL persistence implemented in `models.py`.
- ✅ Basic `TaskIQExecutor` implemented with step dispatching and result polling.
- ✅ Repository updated to use TaskIQ executor as default.
- ✅ Basic unit tests implemented.
- ❌ **Still needs work**: Exponential backoff, visibility timeout handling, public API usage, interface-level testing.

## Remaining Tasks

1. **Add exponential backoff for broker reconnection**
    - Implement jittered exponential backoff in `LocalStackSqsBroker` for startup and reconnection failures.
    - Add configurable retry parameters to settings.

2. **Implement visibility timeout handling**
    - Add background task to detect `RUNNING` tasks stuck longer than `settings.taskiq_visibility_timeout`.
    - Re-mark stuck tasks as `PENDING` to allow re-execution.

3. **Replace internal API usage with public APIs**
    - Remove imports from `dagster._core` in executor.
    - Find public alternatives to `StepFailureData`, `StepSuccessData`, and `StepKind`.
    - Ensure executor uses only public Dagster APIs.

4. **Convert to interface-level testing**
    - Replace current unit tests with end-to-end tests that exercise full job execution.
    - Focus on Dagster Job behavior rather than internal component testing.
    - Use in-memory broker stubs to avoid LocalStack dependencies.

## Exit Criteria
- `dagster_taskiq.taskiq_executor` exports `TaskIQExecutor`, payload dataclasses, and a LocalStack-aware broker wrapper.
- Dagster jobs default to the TaskIQ executor through `Definitions` configuration.
- Idempotency storage handles exactly-once semantics with visibility timeout recovery.
- Broker implements exponential backoff for resilient operation.
- Interface-level tests pass locally: `cd app && uv run pytest`.
- No usage of `dagster._core` internal APIs in executor.
