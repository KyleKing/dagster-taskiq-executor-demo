# Known Issues and Limitations

**Last Updated**: 2025-11-20

This document consolidates all known issues, limitations, and TODOs across the dagster-taskiq project. Issues are categorized by severity and component.

---

## Critical Issues (Blocking Production Use)

### 1. Queue Routing Not Implemented

**Component**: `dagster-taskiq`
**Severity**: Critical
**Status**: Documented, not fixed

**Description**: The `DAGSTER_TASKIQ_QUEUE_TAG` tag on steps/runs and the launcher's `default_queue` configuration are completely ignored. All tasks route to a single SQS queue regardless of tags.

**Impact**: Cannot route different job types to different queues (critical feature parity gap with dagster-celery).

**Affected Files**:
- `dagster-taskiq/src/dagster_taskiq/core_execution_loop.py:137`
- `dagster-taskiq/src/dagster_taskiq/executor.py:102`
- `dagster-taskiq/src/dagster_taskiq/launcher.py:200`

**Workaround**: Use separate Dagster instances with different queue configurations.

**Tracking**: [PARITY_REVIEW.md](./dagster-taskiq/PARITY_REVIEW.md) - Finding #1

---

### 2. Priority Inversion Bug

**Component**: `dagster-taskiq`
**Severity**: Critical
**Status**: Partially addressed, integration tests failing

**Description**: The executor multiplies priority by 10 to set SQS delay, causing higher priority tasks to wait longer before becoming visible in the queue. This is opposite of the intended behavior.

**Impact**: Performance regression vs dagster-celery, breaks priority-based scheduling.

**Affected Files**:
- `dagster-taskiq/src/dagster_taskiq/executor.py:128`
- `dagster-taskiq/src/dagster_taskiq/executor.py:210-224` (_priority_to_delay_seconds)

**Current Status**:
- Unit tests pass (priority delay calculation works)
- Integration tests fail due to LocalStack DelaySeconds limitations
- Priority mapping implemented but inversion logic needs fixing

**Workaround**: Avoid using priority-based scheduling.

**Tracking**:
- [PARITY_REVIEW.md](./dagster-taskiq/PARITY_REVIEW.md) - Finding #2
- [IMPLEMENTATION_PROGRESS.md](./dagster-taskiq/IMPLEMENTATION_PROGRESS.md) - Phase 1, Item 1

---

### 3. Run Termination Not Supported

**Component**: `dagster-taskiq`
**Severity**: Critical
**Status**: Phase 3 feature (planned)

**Description**: The `TaskiqRunLauncher.terminate()` method always returns `False` and logs "not supported". Cannot cancel running jobs like dagster-celery's `AsyncResult.revoke()`.

**Impact**: Cannot stop long-running or stuck jobs, must wait for completion or manually kill workers.

**Affected Files**:
- `dagster-taskiq/src/dagster_taskiq/launcher.py:124`

**Workaround**: Manually terminate worker processes or delete SQS messages.

**Next Steps**:
- Wire up `CancellableSQSBroker` (already implemented, disabled by default)
- Implement worker-side cancellation checking in core_execution_loop
- Update `supports_resume_run` capability flag

**Tracking**:
- [PARITY_REVIEW.md](./dagster-taskiq/PARITY_REVIEW.md) - Finding #4
- [IMPLEMENTATION_PROGRESS.md](./dagster-taskiq/IMPLEMENTATION_PROGRESS.md) - Phase 3

---

## High Priority Issues

### 4. Worker Health Checks Return UNKNOWN

**Component**: `dagster-taskiq`
**Severity**: High
**Status**: Documented, not fixed

**Description**: Launcher advertises `supports_check_run_worker_health = True` but always returns `WorkerStatus.UNKNOWN` because no result backend status is read.

**Impact**: Cannot monitor worker health via Dagster UI, no visibility into worker failures.

**Affected Files**:
- `dagster-taskiq/src/dagster_taskiq/launcher.py:248`

**Workaround**: Monitor workers via CloudWatch logs or custom health check endpoints.

**Next Steps**: Either integrate TaskIQ result backend status polling or set `supports_check_run_worker_health = False`.

**Tracking**: [PARITY_REVIEW.md](./dagster-taskiq/PARITY_REVIEW.md) - Finding #5

---

### 5. Config Source Ignored

**Component**: `dagster-taskiq`
**Severity**: High
**Status**: Documented, not fixed

**Description**: Executor and launcher accept `config_source` parameter in configuration schema, but `make_app()` ignores it and hard-codes SQS/S3 settings.

**Impact**: Misleading configuration options, users cannot customize broker settings via config_source.

**Affected Files**:
- `dagster-taskiq/src/dagster_taskiq/executor.py:151`
- `dagster-taskiq/src/dagster_taskiq/launcher.py:76`
- `dagster-taskiq/src/dagster_taskiq/make_app.py:37`

**Workaround**: None - cannot customize beyond exposed parameters.

**Next Steps**: Either thread config_source through to broker creation or remove from schema entirely.

**Tracking**: [PARITY_REVIEW.md](./dagster-taskiq/PARITY_REVIEW.md) - Finding #3

---

### 6. Docker Dependency in Runtime

**Component**: `dagster-taskiq`
**Severity**: High
**Status**: Marked for removal

**Description**: Project depends on `docker>=7.1.0` with comment "# Find alternative" but usage is unclear.

**Impact**: Heavy unnecessary dependency in production environments.

**Affected Files**:
- `dagster-taskiq/pyproject.toml:14`

**Workaround**: Accept the dependency for now.

**Next Steps**:
1. Identify where Docker SDK is used (likely tests only)
2. Move to dev dependencies or remove entirely
3. Replace with lightweight alternative if needed

**Tracking**: [CLEANUP_REPORT.md](./CLEANUP_REPORT.md) - Issue #10

---

## Medium Priority Issues

### 7. CloudWatch Metrics Not Implemented

**Component**: `dagster-taskiq-demo`
**Severity**: Medium
**Status**: TODO in code

**Description**: Metrics module has placeholder TODO for CloudWatch publishing using boto3.

**Impact**: No production metrics/monitoring via CloudWatch.

**Affected Files**:
- `dagster-taskiq-demo/src/dagster_taskiq_demo/config/metrics.py:59`

**Workaround**: Use structured logs or custom metrics solution.

**Code**:
```python
# TODO: Implement CloudWatch publishing using boto3
```

**Tracking**: [CLEANUP_REPORT.md](./CLEANUP_REPORT.md) - Issue #11

---

### 8. Worker Cancellation Incomplete

**Component**: `dagster-taskiq`
**Severity**: Medium
**Status**: Implemented but disabled (Phase 3)

**Description**: `CancellableSQSBroker` and `CancellableReceiver` exist but are disabled by default and not wired to executor.

**Impact**: Cannot implement graceful task cancellation.

**Affected Files**:
- `dagster-taskiq/src/dagster_taskiq/cancellable_broker.py:19`
- `dagster-taskiq/src/dagster_taskiq/make_app.py:102` (enable_cancellation=False)

**Code**:
```python
# TODO: Implement worker-side cancellation checking in core_execution_loop.py
```

**Next Steps** (Phase 3):
1. Wire CancellableSQSBroker into make_app() when cancellation enabled
2. Start cancel listener in core_execution_loop
3. Cancel pending results when messages arrive
4. Add integration tests

**Tracking**: [IMPLEMENTATION_PROGRESS.md](./dagster-taskiq/IMPLEMENTATION_PROGRESS.md) - Phase 3

---

### 9. Auto-Scaler Configuration Gap

**Component**: `dagster-taskiq-demo`
**Severity**: Medium
**Status**: TODO in code

**Description**: Cannot disable failure simulation for production-like tests.

**Impact**: Testing scenarios always include failure injection.

**Affected Files**:
- `dagster-taskiq-demo/src/dagster_taskiq_demo/auto_scaler/__init__.py:320`

**Code**:
```python
# TODO: Add settings for failure simulation enable/disable and probability
```

**Workaround**: Manually modify code to disable failure injection.

**Tracking**: [CLEANUP_REPORT.md](./CLEANUP_REPORT.md) - Issue #15

---

### 10. Query Attribute Assumptions

**Component**: `dagster-taskiq-demo`
**Severity**: Medium
**Status**: Investigation needed

**Description**: Unclear why certain attributes are None, needs investigation.

**Impact**: Potential configuration issue with Dagster instance.

**Affected Files**:
- `dagster-taskiq-demo/src/dagster_taskiq_demo/main.py:113`

**Code**:
```python
# TODO: is this really necessary? If so, why are these attributes None?
```

**Tracking**: [CLEANUP_REPORT.md](./CLEANUP_REPORT.md) - Issue #16

---

## Low Priority / Environmental Issues

### 11. LocalStack SQS DelaySeconds Unreliable

**Component**: Testing infrastructure
**Severity**: Low (doesn't affect production)
**Status**: Documented limitation

**Description**: LocalStack's SQS implementation doesn't reliably honor DelaySeconds parameter, causing integration test failures.

**Impact**:
- Integration tests flaky with LocalStack
- Cannot fully test priority/delay features locally
- Unit tests pass, integration tests fail

**Affected Tests**:
- `tests/test_priority.py::test_run_priority_job`

**Workaround**:
- Use unit tests with mocked SQS for delay testing
- Use real AWS SQS for integration testing
- Document limitation for contributors

**Tracking**: [IMPLEMENTATION_PROGRESS.md](./dagster-taskiq/IMPLEMENTATION_PROGRESS.md) - Line 20

---

### 12. S3 Extended Payloads Untested

**Component**: `dagster-taskiq`
**Severity**: Low
**Status**: Implemented but not verified

**Description**: S3 extended payload support (for messages >256KB) is configured but has no smoke tests against LocalStack.

**Impact**: Unknown if large message handling works correctly.

**Next Steps**:
1. Create test with >256KB payload
2. Run against LocalStack
3. Document findings

**Tracking**: [IMPLEMENTATION_PROGRESS.md](./dagster-taskiq/IMPLEMENTATION_PROGRESS.md) - Immediate Priorities, Item 1

---

### 13. Pydantic Version Constraints

**Component**: `dagster-taskiq`
**Severity**: Low
**Status**: Known compatibility issue

**Description**: Pydantic pinned to `>=2.10.0,<=2.11.0` with comment "# FYI: issues with dependencies".

**Impact**: Cannot use newer Pydantic versions, may have dependency conflicts.

**Affected Files**:
- `dagster-taskiq/pyproject.toml`

**Workaround**: Accept version constraint.

**Next Steps**: Document which dependencies cause issues, test with newer versions when available.

**Tracking**: [CLEANUP_REPORT.md](./CLEANUP_REPORT.md) - Architecture Inconsistency #3

---

## Documentation Issues

### 14. taskiq-demo/PLAN.md is Stale

**Component**: Documentation
**Severity**: Low
**Status**: Needs archival

**Description**: PLAN.md describes implementation that's already complete, causing confusion.

**Impact**: Contributors may think work is still pending.

**Affected Files**:
- `taskiq-demo/PLAN.md`

**Next Steps**: Move to `PLAN_ARCHIVE.md` or delete if no historical value.

**Tracking**: [CLEANUP_REPORT.md](./CLEANUP_REPORT.md) - Issue #20

---

## Feature Parity Gaps vs dagster-celery

Complete feature parity analysis: [PARITY_REVIEW.md](./dagster-taskiq/PARITY_REVIEW.md)

### Not Yet Implemented
- ❌ Queue routing via tags
- ❌ Task cancellation/revocation
- ❌ Worker health checks
- ❌ Config source support
- ❌ CLI commands: worker status, worker terminate

### Architecture Differences (By Design)
- ✅ Uses SQS instead of Redis/RabbitMQ
- ✅ Async-first with asyncio
- ✅ Custom workers (not TaskIQ framework)
- ✅ Result polling via idempotency storage
- ✅ AWS-specific configuration

---

## Implementation Roadmap

### Phase 1: Stabilize Core Behavior ✅ Mostly Complete
- ✅ Delay/priority mapping implemented
- ✅ Fair queue guards
- ✅ Waiter task cleanup
- ⚠️ Integration tests flaky (LocalStack limitation)

### Phase 2: Complete TaskIQ API Adoption 🔄 In Progress
- ✅ Broker simplification
- ✅ Cancellation preparation (disabled)
- ✅ Independent test infrastructure
- ⏸️ Config source threading (pending decision)

### Phase 3: Implement Cancellation ⏸️ Planned
- ⏸️ Executor integration
- ⏸️ Dagster-facing API
- ⏸️ Worker handling
- ⏸️ Testing

See [IMPLEMENTATION_PROGRESS.md](./dagster-taskiq/IMPLEMENTATION_PROGRESS.md) for detailed status.

---

## How to Report New Issues

1. Check if issue is already documented in this file
2. For bugs: Open GitHub issue with reproducible example
3. For feature requests: Discuss in PARITY_REVIEW.md or IMPLEMENTATION_PROGRESS.md
4. For documentation: Update relevant README or this file

---

## Issue Resolution Process

When an issue is fixed:

1. Update status in this document
2. Remove TODO comment from code
3. Add tests to prevent regression
4. Update IMPLEMENTATION_PROGRESS.md if applicable
5. Document in CHANGELOG (when created)
6. Update relevant README files

---

## Quick Reference

**By Severity**:
- **Critical** (3): Queue routing, Priority inversion, Run termination
- **High** (3): Worker health checks, Config source, Docker dependency
- **Medium** (4): CloudWatch metrics, Cancellation, Auto-scaler config, Query attributes
- **Low** (3): LocalStack limitations, S3 payloads, Pydantic constraints

**By Component**:
- **dagster-taskiq** (8 issues): Core executor implementation
- **dagster-taskiq-demo** (3 issues): Demo application
- **Infrastructure** (2 issues): LocalStack, testing

**By Status**:
- **Documented, not fixed** (6): Awaiting implementation
- **In progress** (2): Actively being worked on
- **Planned** (3): Phase 3 roadmap items
- **Investigation needed** (2): Root cause unclear
