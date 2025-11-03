# TaskIQ Demo Implementation Plan

## Goals

- Showcase a minimal TaskIQ deployment that uses `taskiq-aio-sqs` against LocalStack SQS.
- Run both the FastAPI ingress service and the TaskIQ worker on ECS via the existing LocalStack-based infrastructure toolchain.
- Create new ECS, SQS, IAM, and other resources in Pulumi (../deploy/__main__.py) following the same patterns as the Dagtser-TaskIQ demo (shared the ECS Cluster and other high-level services)
- Demonstrate async sleep tasks with configurable durations (between 1s and 5 min) and expose a simple API to enqueue work.
- Keep the codebase intentionally slim compared to `dagster-taskiq-demo` while reusing compatible tooling (`uv`, `mise`, Docker Bake).

## Architecture Overview

- **FastAPI service**: Receives `POST /tasks` requests with payload `{duration_seconds}` and enqueues TaskIQ tasks. Runs under ECS Fargate (LocalStack) with an ALB.
- **TaskIQ worker**: Uses `taskiq` CLI with `SQSAsyncBroker` from `taskiq-aio-sqs` to poll the queue and execute async tasks that `asyncio.sleep` for the requested duration. Emits structured logs for start/finish.
- **Shared package**: Single Python project that exposes both the FastAPI app and TaskIQ task definitions, so the image can launch either role based on a command/env var.
- **Configuration**: Environment-driven (LocalStack endpoint, queue name, visibility timeout, etc.) stored in a small settings module.

## Implementation Steps

**Important: Adapt code from ../dagster-taskiq-demo**

### 1. Scaffold directory and tooling

- Add `taskiq-demo/pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `taskiq`, `taskiq-aio-sqs`, `aioboto3`, `pydantic-settings`, and `structlog`, and for testing `pytest`, `httpx`.
- Create `mise.toml` to expose tasks: `run app`, `run worker`, `format`, `lint`, `test`.

### 2. Application package structure (`src/taskiq_demo/`)

- `__init__.py`: minimal exports.
- `config.py`: Pydantic settings for SQS endpoint/queue, AWS creds (default LocalStack), logging level, sleep duration defaults.
- `logging.py`: configure structlog JSON logs shared by both entrypoints.
- `tasks.py`: define TaskIQ broker (`SQSAsyncBroker`), TaskIQ dispatcher, and the async sleep task (`@task`).
- `service.py`: FastAPI application with endpoints to enqueue sleeps and report queue health (optional `GET /health`).
- `worker.py`: helper to bootstrap logging and run the TaskIQ worker (wrapping `taskiq.worker.run_worker` or CLI invocation).

### 3. Runtime entrypoints & packaging

- Provide CLI scripts in `pyproject` (`[project.scripts]`) for `taskiq-demo-api` and `taskiq-demo-worker`.
- Add `Dockerfile` that builds a single image with `uv`/`pip`, copies source, and selects command via env (`SERVICE_ROLE=api|worker`).
- Update/extend `docker-bake.hcl` to include the new image definition if required by existing build pipeline.
- Provide `entrypoint.sh` (if needed) to dispatch between API and worker commands.

### 4. Local development ergonomics

- Document `.env.example` with LocalStack defaults (AWS access key, secret, region, SQS endpoint, queue name).
- Add `README.md` within `taskiq-demo/` describing local run commands (`uv run taskiq-demo-api`, `uv run taskiq-demo-worker`, `mise run app`).
- Include `tests/` directory with:
  - FastAPI client test to assert enqueue endpoint returns 202 and pushes message (mock broker).
  - Task execution test verifying sleep task respects duration metadata (use `asyncio` and patch `asyncio.sleep`).

### 5. Infrastructure integration (deploy/)

- Introduce new Pulumi module `deploy/modules/taskiq_demo.py` that provisions:
  - SQS FIFO (or standard) queue for TaskIQ.
  - ECS task definitions/services for API and worker, sharing the same container image but different commands.
  - IAM roles/policies granting SQS access.
  - Optional ALB or output of service endpoint.
- Wire the module into the root stack (alongside existing Dagster components) guarded behind config flags so it can be deployed independently.
- Ensure Pulumi config exposes queue name, desired counts, and image tag parameters.

### 6. Validation & automation

- Add `mise run demo` or `mise run deploy-taskiq-demo` to orchestrate LocalStack start, Pulumi up for the new module, and health checks (if effort is reasonable).
- Extend CI/test scripts (if any) to include the new directory (`mise run checks` should cover `taskiq-demo`).
- Provide manual verification steps in the README: deploy stack, curl the API endpoint, observe worker logs completing sleep.

## Open Questions / Follow-ups

- Should the SQS queue be FIFO (for ordering/dedup) or standard? Default to standard unless idempotency is required.
- Do we reuse existing VPC/cluster definitions from `dagster-taskiq-demo` Pulumi modules or create isolated ones? Tentative plan: reuse shared networking resources for simplicity.
- Is CloudWatch logging required for the demo? If yes, configure log groups in Pulumi.
- Determine whether to publish metrics (e.g., Prometheus) or rely solely on logging for the demo.

## Risks & Mitigations

- **TaskIQ worker stability**: ensure graceful shutdown handling and visibility timeout configuration to avoid duplicate execution; include tests around broker settings.
- **Pulumi complexity creep**: keep module minimal and optional; defer advanced autoscaling to future work.
- **LocalStack limits**: validate `taskiq-aio-sqs` compatibility with LocalStack (may require custom endpoint URL); document fallbacks if issues arise.
