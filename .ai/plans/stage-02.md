# Stage 02 – TaskIQ Worker Runtime

## Goals
- Build the TaskIQ worker service that consumes executor payloads, runs Dagster ops, and reports results.
- Provide operational entrypoints and container wiring so ECS services created by Pulumi can run workers.

## Current State
- Stage 01 will expose payload contracts and the `DagsterTaskIQExecutor`.
- `app/src/dagster_taskiq/taskiq_executor` lacks a worker implementation, CLI entrypoints, or feedback channel to Dagster.
- Pulumi module `deploy/modules/taskiq.py` creates an ECS task definition but the container currently has no worker command or health endpoints.

## Tasks
1. **Implement TaskIQ application wiring**
   - Create a module (e.g., `taskiq_executor/app.py`) defining a `TaskiqApp` bound to the LocalStack SQS broker wrapper.
   - Register a consumer function (e.g., `@taskiq_app.task`) that accepts `OpExecutionTask`, rehydrates Dagster execution context, and invokes the target step.
   - Reuse Dagster's `reconstructable` or `execute_step` APIs to execute work using the same repository code deployed in the container.

2. **Result reporting and acknowledgment**
   - Upon success, write completion events back via Dagster instance APIs (`report_engine_event`, `handle_new_event`) and update idempotency state.
   - On failure, capture traceback, increment retry counters, and decide whether to requeue, dead-letter, or mark as failed.
   - Ensure the worker explicitly deletes the SQS message only after durable result persistence.

3. **Operational controls**
   - Add graceful shutdown handling (catch `SIGTERM`/`SIGINT`, finish in-flight tasks, flush logs).
   - Expose a lightweight HTTP/health check endpoint inside the container for ECS health probes (reuse `aiohttp` or `fastapi` if needed, otherwise simple `asyncio.start_server`).
   - Respect settings such as `taskiq_worker_concurrency` and `taskiq_visibility_timeout`.

4. **Container & CLI integration**
   - Provide an executable entrypoint (e.g., `python -m dagster_taskiq.taskiq_executor.worker` or a console script) that starts the TaskIQ worker loop.
   - Update `app/Dockerfile` to include the new entrypoint and configure `CMD`/`ENTRYPOINT` overrides for worker vs. daemon tasks.
   - Adjust Pulumi `create_taskiq_infrastructure` to set `command`/`entryPoint` for the ECS container, inject queue URLs via environment variables, and configure health check command to hit the new endpoint.

5. **Testing**
   - Add integration-style tests that invoke the worker task function directly with a fake Dagster instance and broker stub.
   - Mock SQS interactions using `botocore.stub` or a purpose-built FIFO queue stub to keep tests fast.
   - Validate graceful shutdown path via unit test (e.g., simulate cancel scopes).

## Exit Criteria
- Worker code can execute Dagster ops dispatched by the executor and persist outcomes.
- ECS worker task definition uses the new worker command and passes health checks.
- Tests covering worker execution, result handling, and idempotency updates pass locally.
- Documentation in `AGENTS.md`/`README.md` updated to explain how to run the worker service.
