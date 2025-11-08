# Remaining Work and Known Issues

This file consolidates remaining work and known issues from `dagster-taskiq/IMPLEMENTATION_PROGRESS.md` and `dagster-taskiq/PARITY_REVIEW.md`.

## High Priority

### Queue Routing Tags Not Implemented
- **Issue**: `DAGSTER_TASKIQ_QUEUE_TAG` on steps/runs is not used when calling `task.kiq(...)`. All tasks go to the single broker queue regardless of tags.
- **Location**: `dagster_taskiq/core_execution_loop.py:137`, `dagster_taskiq/executor.py:102`, `dagster_taskiq/launcher.py:200`
- **Status**: Not started
- **Action**: Implement queue selection parity by mapping Dagster tags to SQS queue selection (per-run and per-step)

### S3 Extended Payloads ✅ Tested
- **Status**: Smoke test implemented (`dagster-taskiq/tests/test_queues.py:59-87`)
- **Note**: Configuration verified, large messages (>256KB) handled via S3 extended payloads

## Medium Priority

### config_source Dropped
- **Issue**: Executor/launcher accept `config_source` but `make_app()` ignores it and hard-codes SQS/S3 settings.
- **Location**: `dagster_taskiq/make_app.py:37`
- **Status**: Not started
- **Action**: Thread `config_source` (and `DEFAULT_CONFIG` values) through to broker creation or clearly remove the option

### Run Termination ✅ Complete
- **Status**: Fully implemented - Launcher `terminate()` method sends cancellation requests, `CancellableReceiver` handles worker-side cancellation
- **Implementation**: `dagster_taskiq/launcher.py:124-194` (terminate), `dagster_taskiq/cancellable_receiver.py` (worker-side)
- **Testing**: Integration test verifies cancellation flow (`test_launcher.py:211-245`)

### Worker Health Check Returns UNKNOWN
- **Issue**: Launcher advertises `supports_check_run_worker_health = True` but always returns `WorkerStatus.UNKNOWN` because no result backend status is read.
- **Location**: `dagster_taskiq/launcher.py:248`, `launcher.py:328`
- **Status**: Not started
- **Action**: Either integrate TaskIQ result backend status or flip the capability flag to `False`

## Low Priority / Optional Improvements

### Result Handling Simplification
- **Current**: `is_ready()`/`wait_result()` pattern works correctly
- **Improvement**: Could explore TaskIQ async helpers for cleaner code
- **Status**: Low priority - current implementation is stable

### Broker Configuration Ergonomics
- **Current**: Config schema functional
- **Improvement**: Could add validation for common misconfigurations, improve error messages for queue/broker mismatch
- **Status**: Low priority

### Documentation Improvements
- Add config examples showing FIFO queue usage
- Document `is_fair_queue` toggle behavior
- Update README with cancellation roadmap

## Phase 3 - Cancellation (Not Started)

Blocked until Phases 1-2 complete and LocalStack issues resolved:

1. **Executor integration**
   - Wire `CancellableSQSBroker` into `make_app()` when cancellation enabled
   - Start cancel listener in `core_execution_loop`; cancel pending results when messages arrive

2. **Dagster-facing API**
   - Add method on `TaskiqExecutor`/instance to submit cancel requests (wrap `cancel_task`)
   - Ensure run launcher or daemon surfaces cancellation path

3. **Worker handling**
   - Extend `tasks.create_task` workers to check cancellation signal before executing steps
   - Decide on cooperative interruption strategy for long-running steps

4. **Testing**
   - Add integration test using LocalStack cancelling an in-flight step
   - Verify idempotency storage still ensures exactly-once semantics after cancellation

## Fixed Issues

### Fair Queue Guards ✅
- **Status**: Complete
- **Implementation**: Auto-detects `.fifo` suffix in queue URL, warns if `is_fair_queue=True` requested on non-FIFO queue

### Waiter Task Cleanup ✅
- **Status**: Complete
- **Implementation**: `_cancel_waiters()` function in `core_execution_loop.py:124-137`

### Broker Simplification ✅
- **Status**: Complete
- **Implementation**: Replaced custom `create_sqs_broker` with `SqsBrokerConfig` dataclass, direct `taskiq_aio_sqs.SQSBroker` construction

## References

- For testing procedures and known limitations: See `TESTING.md`
- For implementation details: See `dagster-taskiq/IMPLEMENTATION_PROGRESS.md` (historical)
- For parity comparison: See `dagster-taskiq/PARITY_REVIEW.md` (historical)

