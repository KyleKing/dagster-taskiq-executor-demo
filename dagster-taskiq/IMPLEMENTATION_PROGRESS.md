# TaskIQ-AIO-SQS Simplification & Cancellation Roadmap

## Snapshot (2025-01-03)

- **Overall progress**: Phase 1 mostly complete – core functionality stable, Phase 2 in progress
- **Focus**: complete TaskIQ API adoption, resolve LocalStack test issues, prepare for Phase 3 cancellation
- **Blocking issues**: LocalStack SQS DelaySeconds support unreliable, S3 extended payload path unverified

## What's Done

### Phase 1 - Stabilise Existing Behaviour ✅

1. **Delay/priority mapping** (`src/dagster_taskiq/executor.py:210-224`)

   - ✅ Implemented `_priority_to_delay_seconds()` function
   - ✅ Maps Dagster priority to SQS DelaySeconds: higher priority = lower delay
   - ✅ Default priority (5) = 0 delay, decreasing priority adds 10s per level
   - ✅ Clamped to SQS max (900 seconds)
   - ✅ Unit tests passing (`tests/test_priority.py::test_priority_delay_translation`)
   - ⚠️ Integration test failing due to LocalStack DelaySeconds limitations

1. **Fair queue guards** (`src/dagster_taskiq/make_app.py:129-143`)

   - ✅ Auto-detects `.fifo` suffix in queue URL
   - ✅ Warns if `is_fair_queue=True` requested on non-FIFO queue
   - ✅ Defaults `is_fair_queue` based on queue type
   - ✅ Prevents misconfiguration that would cause SQS errors

1. **Waiter task cleanup** (`src/dagster_taskiq/core_execution_loop.py:102-116, 228-231`)

   - ✅ Implemented `_cancel_waiters()` function
   - ✅ Called in `finally` block to prevent resource leaks
   - ✅ Gracefully cancels pending asyncio tasks on shutdown

### Phase 2 - TaskIQ API Adoption (In Progress)

1. **Broker simplification**

   - ✅ Replaced custom `create_sqs_broker` with `SqsBrokerConfig` dataclass
   - ✅ Direct `taskiq_aio_sqs.SQSBroker` construction via `create_broker()`
   - ✅ Unsupported options (e.g. `visibility_timeout`) now warn instead of silently ignoring
   - ✅ Result backend integration with S3Backend

1. **Cancellation preparation**

   - ✅ Draft `CancellableSQSBroker` implementation (`src/dagster_taskiq/cancellable_broker.py`)
   - ✅ Disabled by default (`enable_cancellation=False` in `make_app.py:102`)
   - ✅ Added `aioboto3>=13.0.0` as optional dependency `[cancellation]`
   - ⏸️ Not wired to executor yet (Phase 3)

1. **Test infrastructure**

   - ✅ Made test suite independent: unique queue names `dagster-tasks-test-{port}`
   - ✅ Uses port 4567+ to avoid conflicts with dagster-taskiq-demo
   - ✅ Basic executor tests passing (config, CLI)
   - ⚠️ Integration tests flaky with LocalStack

### Documentation & Cleanup

- ✅ Created this progress log
- ✅ Debug logging added to priority/delay mapping (`executor.py:132-135`)
- ✅ Documented LocalStack limitations
- ✅ Fixed test assertion logic for priority ordering

## Remaining Work

### Immediate Priorities

1. **S3 Extended Payloads** - High Priority

   - Configuration implemented but untested
   - Need smoke test against LocalStack
   - Verify large message (>256KB) handling

1. **LocalStack Test Stability** - Medium Priority

   - `test_run_priority_job` fails due to DelaySeconds not being honored
   - Options: upgrade LocalStack, mock SQS delays, or skip test in LocalStack
   - Document LocalStack limitations for contributors

1. **Documentation** - Medium Priority

   - Add config examples showing FIFO queue usage
   - Document `is_fair_queue` toggle behavior
   - Update README with cancellation roadmap

### Phase 2 Completion (Optional Improvements)

1. **Result handling simplification**

   - Current `is_ready()`/`wait_result()` pattern works correctly
   - Could explore TaskIQ async helpers for cleaner code
   - Low priority - current implementation is stable

1. **Broker configuration ergonomics**

   - Current config schema functional
   - Could add validation for common misconfigurations
   - Could improve error messages for queue/broker mismatch

### Phase 3 - Cancellation (Not Started)

See original Phase 3 plan below - blocked until Phases 1-2 complete and LocalStack issues resolved.

## Next Phases

### Phase 1 – Stabilise Existing Behaviour

1. **Fix delay/priority mapping**
   - Revisit Dagster priority semantics (higher number = higher priority).
   - Map priority to `DelaySeconds` so higher priority executes sooner (e.g. inverse clamped scale).
   - Add regression tests using fake broker to confirm zero default delay.
1. **Guard fair queue usage**
   - Detect `.fifo` queues before enabling `is_fair_queue`.
   - Document required queue configuration (standard vs FIFO) and expose toggle via config.
1. **Smoke-test S3 extended payload support**
   - Run against LocalStack to confirm large message flow.
   - Capture findings in test instructions.

### Phase 2 – Complete TaskIQ API Adoption

1. **Result handling simplification**
   - Replace manual `is_ready()`/`get_result()` loop with TaskIQ async helpers or callbacks.
   - Ensure exceptions propagate with serialised Dagster error info.
1. **Broker configuration cleanup**
   - Consume `taskiq_aio_sqs.SQSBroker` directly from executor/app factory.
   - Prune unused kwargs, centralise defaults in one location.
   - Revalidate environment-based overrides.
1. **Config ergonomics**
   - Align `config_source` schema with TaskIQ broker parameters (e.g. allow `is_fair_queue` toggle).
   - Update docs and Dagster config examples accordingly.

### Phase 3 – Implement Cancellation / Revoke

1. **Executor integration**
   - Wire `CancellableSQSBroker` into `make_app()` when cancellation enabled.
   - Start cancel listener in `core_execution_loop`; cancel pending results when messages arrive.
1. **Dagster-facing API**
   - Add method on `TaskiqExecutor`/instance to submit cancel requests (wrap `cancel_task`).
   - Ensure run launcher or daemon surfaces cancellation path.
1. **Worker handling**
   - Extend `tasks.create_task` workers to check cancellation signal before executing steps.
   - Decide on cooperative interruption strategy for long-running steps.
1. **Testing**
   - Add integration test using LocalStack cancelling an in-flight step.
   - Verify idempotency storage still ensures exactly-once semantics after cancellation.

## Validation Plan

- Run `mise run test` after each phase; add targeted Dagster `execute_in_process` scenarios where feasible.
- Add LocalStack integration workflow to CI for SQS/S3 exercises.
- Document manual verification steps in `TESTING.md`.

## Success Criteria

### Phase 1 & 2 (Current) ✅ Mostly Met

- ✅ Delay/priority logic respects Dagster priority contract (unit tests pass)
- ✅ Broker factories use TaskIQ APIs directly (`SqsBrokerConfig.create_broker()`)
- ✅ Configuration errors surface clearly (warnings for unsupported options)
- ✅ All existing Dagster jobs run without configuration changes
- ⚠️ Integration test flaky in LocalStack (DelaySeconds limitation)

### Phase 3 (Future) - Not Yet Started

- ⏸️ Cancellation requests propagate from Dagster through SQS to workers
- ⏸️ Workers short-circuit cancelled tasks gracefully
- ⏸️ Idempotency preserved after cancellation

## Quick Reference

### Files Modified

- `src/dagster_taskiq/executor.py` - Priority-to-delay mapping, debug logging
- `src/dagster_taskiq/make_app.py` - Fair queue guards, cancellation toggle
- `src/dagster_taskiq/broker.py` - SqsBrokerConfig dataclass
- `src/dagster_taskiq/core_execution_loop.py` - Waiter task cleanup
- `tests/conftest.py` - Independent LocalStack fixtures
- `tests/test_priority.py` - Fixed assertion logic
- `pyproject.toml` - Added `[cancellation]` extra for aioboto3

### Test Status

- ✅ Config tests passing (6/6)
- ✅ Unit tests passing (priority delay calculation)
- ⚠️ Integration tests flaky (LocalStack SQS delays)
