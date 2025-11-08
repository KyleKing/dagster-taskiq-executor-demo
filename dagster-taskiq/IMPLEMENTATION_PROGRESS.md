# TaskIQ-AIO-SQS Simplification & Cancellation Roadmap

## Snapshot (2025-01-03)

- **Overall progress**: Phase 1 mostly complete – core functionality stable, Phase 2 in progress
- **Focus**: complete TaskIQ API adoption, resolve LocalStack test issues, prepare for Phase 3 cancellation
- **Blocking issues**: LocalStack SQS DelaySeconds support unreliable, S3 extended payload path unverified

## What's Done

### Phase 1 - Stabilise Existing Behaviour ✅

1. **Priority/queue simplification**

   - ✅ Removed priority-to-delay mapping functionality
   - ✅ Removed multi-queue support
   - ✅ Simplified to single queue implementation

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
- ✅ Removed priority and queue routing functionality
- ✅ Documented LocalStack limitations

## Remaining Work

### Immediate Priorities

1. **S3 Extended Payloads** - High Priority

   - Configuration implemented but untested
   - Need smoke test against LocalStack
   - Verify large message (>256KB) handling

1. **LocalStack Test Stability** - Medium Priority

   - Priority tests removed as part of simplification
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

## Remaining Work

**Note**: For current status and consolidated remaining work, see `../TODO.md`.

The sections below are historical. Completed work has been moved to "Fixed Issues" in `../TODO.md`.

## Validation Plan

- Run `mise run test` after each phase; add targeted Dagster `execute_in_process` scenarios where feasible.
- Add LocalStack integration workflow to CI for SQS/S3 exercises.
- ✅ Manual verification steps documented in `../TESTING.md`.

## Success Criteria

### Phase 1 & 2 (Current) ✅ Mostly Met

- ✅ Simplified to single queue without priority logic
- ✅ Broker factories use TaskIQ APIs directly (`SqsBrokerConfig.create_broker()`)
- ✅ Configuration errors surface clearly (warnings for unsupported options)
- ✅ All existing Dagster jobs run without configuration changes

### Phase 3 (Future) - Not Yet Started

- ⏸️ Cancellation requests propagate from Dagster through SQS to workers
- ⏸️ Workers short-circuit cancelled tasks gracefully
- ⏸️ Idempotency preserved after cancellation

## Quick Reference

### Files Modified

- `src/dagster_taskiq/executor.py` - Removed priority-to-delay mapping
- `src/dagster_taskiq/make_app.py` - Fair queue guards, cancellation toggle
- `src/dagster_taskiq/broker.py` - SqsBrokerConfig dataclass
- `src/dagster_taskiq/core_execution_loop.py` - Removed priority/queue logic, waiter task cleanup
- `tests/conftest.py` - Independent LocalStack fixtures
- `tests/test_priority.py` - Removed (priority tests deleted)
- `pyproject.toml` - Added `[cancellation]` extra for aioboto3

### Test Status

- ✅ Config tests passing
- ✅ Single queue tests passing
