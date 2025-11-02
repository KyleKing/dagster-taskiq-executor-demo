# Stage 01 – TaskIQ Executor Foundation

## Goals
- Implement the Dagster ⇄ TaskIQ executor pipeline inside the standalone `dagster-taskiq` package so ops can be dispatched through SQS with exactly-once semantics.
- Deliver the execution payload contract that downstream worker and autoscaler stages will consume from both the reusable package and the demo application.

## Current State
- ✅ Dagster configuration, jobs, schedules, and tests for the demo live under `app/src/dagster_taskiq_demo`.
- ✅ Standalone package scaffolding exists in `dagster-taskiq/src/dagster_taskiq` with Apache 2.0 licensing.
- ✅ Task payloads, broker, models, worker, and executor ported to standalone package.
- ✅ Settings already expose SQS queue names, AWS endpoints, and Postgres connection details.
- ✅ Idempotency storage with abstract base class and in-memory implementation.
- ✅ Basic executor logic implemented with step dispatching and result polling.
- ✅ Repository updated to use TaskIQ executor as default for LocalStack demo jobs.
- ✅ CLI entrypoint for running workers.
- ✅ Basic unit tests implemented.
- ❌ **Still needs work**: Implement exponential backoff, visibility timeout handling, public API usage, interface-level testing, actual step execution completion.

## Remaining Tasks

1. **Port executor logic into standalone package**
    - Lift shared payloads, broker, and polling utilities into `dagster_taskiq`.
    - Provide compatibility shims in the demo until imports are updated.
    - Ensure packaging metadata and public API surface are defined before downstream stages consume them.

2. **Add exponential backoff for broker reconnection**
    - Implement jittered exponential backoff in `LocalStackSqsBroker` for startup and reconnection failures.
    - Add configurable retry parameters to settings.

3. **Implement visibility timeout handling**
    - Add background task to detect `RUNNING` tasks stuck longer than `settings.taskiq_visibility_timeout`.
    - Re-mark stuck tasks as `PENDING` to allow re-execution.

4. **Replace internal API usage with public APIs**
    - Remove imports from `dagster._core` in executor.
    - Find public alternatives to `StepFailureData`, `StepSuccessData`, and `StepKind`.
    - Ensure executor uses only public Dagster APIs.

5. **Convert to interface-level testing**
    - Replace current unit tests with end-to-end tests that exercise full job execution.
    - Focus on Dagster Job behavior rather than internal component testing.
    - Use in-memory broker stubs to avoid LocalStack dependencies.

## Exit Criteria
- `dagster_taskiq.taskiq_executor` (standalone package) exports `TaskIQExecutor`, payload dataclasses, and a LocalStack-aware broker wrapper.
- Demo application (`dagster_taskiq_demo`) depends on the packaged executor rather than maintaining a forked copy.
- Idempotency storage handles exactly-once semantics with visibility timeout recovery.
- Broker implements exponential backoff for resilient operation.
- Interface-level tests pass locally: `cd app && uv run pytest`.
- No usage of `dagster._core` internal APIs in executor.
