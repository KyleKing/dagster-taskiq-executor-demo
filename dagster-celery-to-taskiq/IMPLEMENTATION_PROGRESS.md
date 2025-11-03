# TaskIQ-AIO-SQS Simplification & Cancellation Roadmap

## Snapshot (2025-01-02)
- **Overall progress**: in progress – core simplifications incomplete, cancellation not wired
- **Focus**: stabilise queue behaviour, finish TaskIQ API adoption, implement SQS-based cancellation
- **Blocking issues**: cancellation wiring still absent, S3 extended payload path unverified, LocalStack-backed regression coverage flaky

## What’s Done
- Created this progress log to track the migration effort.
- Added a draft `CancellableSQSBroker` with design notes (`src/dagster_taskiq/cancellable_broker.py`) – not yet used by the executor.
- Replaced the `create_sqs_broker` wrapper with `SqsBrokerConfig`, letting `make_app()` construct `taskiq_aio_sqs.SQSBroker` directly and surfacing unsupported options (e.g. `visibility_timeout`) via warnings.

## Gaps & Rework Required
- **Result handling follow-ups** (`src/dagster_taskiq/core_execution_loop.py`): waiter tasks should be cancelled or drained when the execution loop exits to avoid leaks.
- **Priority delays** (`src/dagster_taskiq/executor.py`): need integration coverage that the new delay mapping hits SQS as expected once LocalStack fixtures are stable.
- **Fair queue documentation** (`src/dagster_taskiq/make_app.py`): document the FIFO-only toggle in config examples once broker simplification lands across the docs.
- **S3 extended payloads**: configuration is present but unverified; no integration tests or smoke checks.
- **Cancellation flow**:
  - Broker exposes cancellation queue hooks, but the executor loop never consumes them.
  - No orchestration API to request revokes; no worker-side short-circuit for cancelled tasks.

## Next Phases

### Phase 1 – Stabilise Existing Behaviour
1. **Fix delay/priority mapping**
   - Revisit Dagster priority semantics (higher number = higher priority).
   - Map priority to `DelaySeconds` so higher priority executes sooner (e.g. inverse clamped scale).
   - Add regression tests using fake broker to confirm zero default delay.
2. **Guard fair queue usage**
   - Detect `.fifo` queues before enabling `is_fair_queue`.
   - Document required queue configuration (standard vs FIFO) and expose toggle via config.
3. **Smoke-test S3 extended payload support**
   - Run against LocalStack to confirm large message flow.
   - Capture findings in test instructions.

### Phase 2 – Complete TaskIQ API Adoption
1. **Result handling simplification**
   - Replace manual `is_ready()`/`get_result()` loop with TaskIQ async helpers or callbacks.
   - Ensure exceptions propagate with serialised Dagster error info.
2. **Broker configuration cleanup**
   - Consume `taskiq_aio_sqs.SQSBroker` directly from executor/app factory.
   - Prune unused kwargs, centralise defaults in one location.
   - Revalidate environment-based overrides.
3. **Config ergonomics**
   - Align `config_source` schema with TaskIQ broker parameters (e.g. allow `is_fair_queue` toggle).
   - Update docs and Dagster config examples accordingly.

### Phase 3 – Implement Cancellation / Revoke
1. **Executor integration**
   - Wire `CancellableSQSBroker` into `make_app()` when cancellation enabled.
   - Start cancel listener in `core_execution_loop`; cancel pending results when messages arrive.
2. **Dagster-facing API**
   - Add method on `TaskiqExecutor`/instance to submit cancel requests (wrap `cancel_task`).
   - Ensure run launcher or daemon surfaces cancellation path.
3. **Worker handling**
   - Extend `tasks.create_task` workers to check cancellation signal before executing steps.
   - Decide on cooperative interruption strategy for long-running steps.
4. **Testing**
   - Add integration test using LocalStack cancelling an in-flight step.
   - Verify idempotency storage still ensures exactly-once semantics after cancellation.

## Validation Plan
- Run `mise run test` after each phase; add targeted Dagster `execute_in_process` scenarios where feasible.
- Add LocalStack integration workflow to CI for SQS/S3 exercises.
- Document manual verification steps in `TESTING.md`.

## Success Criteria
- Delay/priority logic respects Dagster priority contract with zero-regression tests.
- Broker factories use TaskIQ APIs directly; configuration errors surface clearly.
- Cancellation requests propagate from Dagster through SQS to workers and halt execution gracefully.
- All existing Dagster jobs run without configuration changes unless opting into FIFO/cancellation features.
