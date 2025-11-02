# Stage 04 – Load Simulation, Observability, and End-to-End Validation

## Goals
- Create the load simulator, observability hooks, and integration tests that demonstrate the full Dagster ⇄ TaskIQ ⇄ ECS workflow under varied scenarios.
- Finalise documentation and operational runbooks for the LocalStack demo.

## Current State
- `app/src/dagster_taskiq_demo/load_simulator/__init__.py` is empty; no scenario orchestration exists.
- Auto-scaler and worker services (Stages 02–03) will expose APIs/settings ready for exercise.
- Documentation (`README.md`, `AGENTS.md`) still reflects the pre-TaskIQ implementation.
- Pulumi stack exports resources but lacks dashboards/validation tooling.

## Tasks
1. **Load simulator implementation**
   - Build scenario definitions matching the spec: steady load, burst load, mixed workloads, worker failure, and network partition simulations.
   - Provide a CLI/entrypoint that can schedule Dagster jobs via GraphQL or Dagster Python APIs (e.g., `submit_run`).
   - Allow scenario configuration via YAML/JSON input or CLI flags for job mix ratios and timings.

2. **Exactly-once verification tooling**
   - Compare submitted task idempotency keys against completion records to ensure no duplicates.
   - Surface discrepancies in logs/metrics; optionally export CSV/JSON reports for demo use.
   - Leverage Dagster event log queries (`instance.get_event_records`) to audit executions.

3. **Observability & metrics**
   - Integrate structured logging across worker, executor, auto-scaler, and simulator using consistent log schemas.
   - Publish key metrics (queue depth, worker counts, run latency) to CloudWatch (or log them if CloudWatch is stubbed).
   - Provide dashboards or instructions for viewing metrics via LocalStack UI/CLI.

4. **Integration & smoke tests**
   - Add pytest scenarios that spin up lightweight broker/worker mocks to validate orchestrated flows (focus on Stage 01–03 contracts).
   - Include CLI-level tests for load simulator argument parsing and validation.
   - Ensure `uv run pytest` remains under acceptable runtime by using mocks and shortened durations.

5. **Infrastructure & documentation updates**
   - Extend Pulumi to package/load the simulator as an optional ECS task or on-demand job (as appropriate for demos).
   - Refresh `README.md`, `AGENTS.md`, and `.kiro/specs/*` notes to capture the final architecture, commands, and operational guidance.
   - Document LocalStack caveats (e.g., Aurora Serverless limitations, dependency on LocalStack Pro).

6. **Operational validation**
   - Produce a runbook describing the full demo workflow: provision infrastructure, start Dagster UI, run simulator scenarios, observe auto-scaler responses, and review metrics.
   - Provide teardown instructions (Pulumi destroy, Docker Compose cleanup) and troubleshooting tips (e.g., recovering from stuck Pulumi locks).

## Exit Criteria
- Load simulator can trigger all required scenarios and integrates with exactly-once validation tooling.
- Observability story is documented and demonstrable within LocalStack constraints.
- Full-stack smoke tests exist and pass (`uv run pytest`) alongside type/lint checks.
- Documentation reflects the final system and guides operators through setup, execution, and teardown.
