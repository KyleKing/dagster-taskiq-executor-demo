# Stage 02 – TaskIQ Worker Runtime

## Goals
- Build the TaskIQ worker service (shipped with the demo app) that consumes executor payloads from the standalone `dagster-taskiq` package, runs Dagster ops, and reports results.
- Provide operational entrypoints and container wiring so ECS services created by Pulumi can run workers.

## Current State
- ✅ Stage 01 exposes payload contracts and the `TaskIQExecutor` within `dagster_taskiq`.
- ✅ Worker application structure implemented in `app/src/dagster_taskiq_demo/taskiq_executor/app.py` with SQS message consumption.
- ✅ CLI entrypoint implemented in `worker.py` for container execution.
- ✅ ECS task definitions updated with worker command and health checks.
- ✅ Graceful shutdown handling and health server implemented.
- ✅ Basic worker tests implemented.
- ❌ **Still needs work**: Actual Dagster step execution (currently simulated), result reporting via Dagster APIs, clean dependency on the new package APIs.

## Remaining Tasks

1. **Implement actual Dagster step execution**
    - Replace simulated execution in `_execute_step()` with real Dagster step execution.
    - Use Dagster's `reconstructable` and `execute_step` APIs to run ops in the worker.
    - Handle step context reconstruction and resource management properly.

2. **Add result reporting via Dagster APIs**
    - Implement proper result reporting using `DagsterInstance.report_engine_event()`.
    - Write completion/failure events back to Dagster's event log.
    - Ensure idempotency state updates happen after successful event reporting.

3. **Implement retry and failure handling**
    - Add logic to decide whether to requeue, dead-letter, or mark tasks as failed.
    - Implement retry counters and exponential backoff for transient failures.
    - Ensure SQS message deletion only after durable result persistence.

4. **Add graceful shutdown for in-flight tasks**
    - Implement proper cancellation of in-flight step executions during shutdown.
    - Wait for current tasks to complete or timeout before shutting down.
    - Handle SIGTERM/SIGINT signals to allow clean worker termination.

## Exit Criteria
- Worker executes actual Dagster ops using proper APIs from `dagster_taskiq`, not the legacy simulation.
- Results are reported back to Dagster via instance APIs and event log.
- Worker handles failures with appropriate retry/dead-letter logic.
- Graceful shutdown completes in-flight tasks before termination.
- ECS worker services run successfully with health checks.
- Integration tests validate end-to-end worker execution flow across the packaged executor and demo worker.
