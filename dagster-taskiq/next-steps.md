# dagster-taskiq Rewrite Proposal

## Purpose
- Deliver a first-class `dagster-taskiq` executor that supersedes the Celery implementation for the LocalStack demo and future production adopters.
- Preserve architectural lessons from `dagster-celery` while realigning the codebase around TaskIQ, SQS, and modern Dagster APIs.
- Comply with Apache License 2.0 obligations when adapting upstream code, ensuring contributors and downstream users inherit clear licensing.

## Licensing & Attribution
- The upstream `dagster-celery` project is Apache-2.0 licensed. Copy the canonical license text into `dagster-taskiq/LICENSE` verbatim and retain all copyright and patent notices.  
  - Reference: [Apache License 2.0 §4](https://www.apache.org/licenses/LICENSE-2.0#redistribution), [Choose a License summary](https://choosealicense.com/licenses/apache-2.0/).
- Create `dagster-taskiq/NOTICE` that (a) mirrors upstream notices, (b) lists files or modules copied from `dagster-celery`, and (c) documents substantive modifications (e.g., “Modified by dagster-taskiq maintainers, 2024, to replace Celery task execution with TaskIQ workers backed by SQS.”).
- In every source file derived from `dagster-celery`, keep the original header comment (if present) and append:
  ```
  # Modifications copyright (c) 2024 dagster-taskiq contributors
  ```
- Track third-party dependencies introduced during the rewrite (TaskIQ, aioboto3, etc.) and ensure their licenses are Apache-compatible. Bundle any required texts in `licenses/`.
- Update `pyproject.toml` / `setup.cfg` classifiers to “Apache Software License” and mention derivative lineage in the package description.

## Technical Rewrite Plan

### 1. Establish Core Package Layout
- Create `dagster_taskiq/` package mirroring `dagster_celery`’s module boundaries where they make sense (e.g., executor, CLI integration, resources).
- Split executor runtime (shared with demo app) into a reusable library consumed by both the LocalStack integration and future PyPI distribution.
- Provide typed public entrypoints:
  - `DagsterTaskIQJobExecutor` implementing Dagster’s executor interface.
  - `SQSTaskIQWorker` (async) wrapping the aioboto3 consumer and idempotency tracker.
  - Configuration helpers for SQS queues, concurrency, heartbeat intervals, retries.

### 2. Replace Celery Primitives with TaskIQ
- Swap Celery app/broker configuration for TaskIQ-compatible SQS abstractions. Reuse idempotency logic already prototyped in `app/src/dagster_taskiq_demo/taskiq_executor/__init__.py`.
- Re-implement message serialization (`OpExecutionTask`) to align with Dagster step payloads and exactly-once semantics.
- Remove Celery task decorators; instead provide TaskIQ-compatible coroutine runners invoked by the worker.
- Replace Celery event/heartbeat handling with Dagster instance event reporting via `report_engine_event` and `DagsterEvent`s.

### 3. Executor Integration
- Implement `execute_step` bridging: convert Dagster `StepExecutionContext` into serialized payloads, publish to SQS, and await completion acknowledgements via the PostgreSQL idempotency table.
- Provide visibility-timeout recovery and exponential backoff policies inside the executor/worker handshake rather than Celery retries.
- Ensure executor uses public Dagster APIs only (no `dagster._core` references).

### 4. Worker Runtime
- Harden the async worker:
  - Message polling loop with jittered backoff and visibility timeout extensions.
  - Run reconstruction using `ReconstructableJob` or `ReconstructableRepository` metadata encoded in the payload.
  - Durable result persistence: write completion/failure events, then delete SQS message once the event is confirmed.
  - Health/metrics endpoints similar to the prototype (HTTP health check, Prometheus metrics HTTP server).

### 5. CLI & Deployment Tooling
- Port Celery CLI entrypoints (`dagster-celery worker`, `dagster-celery start`) to `dagster-taskiq` commands for worker orchestration and queue management.
- Document LocalStack/Docker workflows and provide `mise` tasks for building, testing, and running workers locally.
- Integrate Pulumi stack outputs (queue URLs, IAM credentials) into the worker configuration layer.

### 6. Testing & Validation
- Introduce interface-level tests:
  - In-process Dagster job execution using the TaskIQ executor with stubbed SQS.
  - Integration tests using LocalStack SQS and the async worker event loop.
  - Reliability scenarios (visibility timeout recovery, crash recovery, duplicate message suppression).
- Maintain parity with existing `dagster-celery` test coverage where applicable, adding new cases for TaskIQ-specific behavior.

### 7. Documentation & Release
- Write migration notes for Celery users explaining conceptual differences, supported features, and configuration flags.
- Update README with architecture diagrams, worker lifecycle, and LocalStack demo instructions.
- Prepare packaging metadata (`pyproject.toml`, optional `README.md` long description) and establish release checklist (tagging, changelog, PyPI publishing).

## Milestones
- **M1 – Package Skeleton & Licensing (Week 1)**: License/NOTICE updates, project scaffolding, basic executor/worker modules compiling.
- **M2 – Core Execution Path (Weeks 2-3)**: Dagster step execution, result reporting, idempotency flows implemented with integration tests.
- **M3 – Reliability & Tooling (Weeks 4-5)**: Backoff, visibility timeout, CLI, documentation, LocalStack demo parity.
- **M4 – Release Readiness (Week 6)**: Final QA, docs complete, publish alpha version, deprecate Celery paths in demo.

## Risks & Mitigations
- **API Drift**: Continuous validation against Dagster public APIs with compatibility tests on supported versions.
- **Licensing Oversight**: Maintain a review checklist for every copied file; run diff audits to confirm attribution.
- **Operational Gaps**: Early integration with LocalStack to surface deployment issues; add observability features (logs, metrics).
- **Community Adoption**: Provide migration guides and highlight benefits (SQS compatibility, exactly-once semantics) to encourage testing.

## Next Actions
1. Finalize LICENSE, NOTICE, and attribution headers in the new package.
2. Port executor scaffolding into `dagster_taskiq` and consolidate shared utilities from the demo (`taskiq_executor/__init__.py`).
3. Begin M2 implementation tasks per Stage 01-02 plan, coordinating updates to `.ai/plans` for standalone packaging milestones.

