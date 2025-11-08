# Dagster TaskIQ vs Dagster Celery Parity Review

## Findings (Action Required)

- **Queue routing and priority removed** – Multi-queue support and priority-based task scheduling have been removed to simplify the implementation. All tasks now use a single SQS queue without priority-based delays.
- **`config_source` dropped (Medium)** – Executor/launcher wrap user `config_source`, but `make_app` ignores it and hard-codes SQS/S3 settings (`dagster_taskiq/executor.py:151`, `dagster_taskiq/launcher.py:76`, `dagster_taskiq/make_app.py:37`). Thread `config_source` (and `DEFAULT_CONFIG` values) through to broker creation or clearly remove the option.
- **Run termination unsupported (Medium)** – Celery revoked tasks via `AsyncResult.revoke`; TaskIQ now logs "not supported" and returns `False` (`dagster_taskiq/launcher.py:124`). Implement termination (e.g. by sending cancel messages via `CancellableSQSBroker`) or document the limitation and adjust `supports_resume_run`/`terminate` expectations.
- **Worker health check regressed (Medium)** – Launcher still advertises `supports_check_run_worker_health = True`, but always returns `WorkerStatus.UNKNOWN` because no result backend status is read (`dagster_taskiq/launcher.py:248`). Either integrate TaskIQ result backend status or flip the capability flag to `False`.

## Next Steps

**Note**: This document is historical. For current status and remaining work, see `../TODO.md` and `../TESTING.md`.

1. ✅ Queue routing and priority removed - Simplified to single queue implementation
1. Decide how `config_source` should work with TaskIQ. If configurable knobs exist, pass them through; if not, remove the field from schemas to avoid misleading users. (See `../TODO.md`)
1. Design a termination path (leveraging `CancellableSQSBroker`/`CancellableReceiver`) or explicitly mark termination unsupported in both code and docs. (See `../TODO.md` Phase 3)
1. Update `supports_check_run_worker_health` to reflect real capabilities; add backend polling if feasible so health checks return SUCCESS/FAILED/RUNNING like Celery. (See `../TODO.md`)
1. Audit CLI parity: reintroduce equivalents for `worker terminate/status` or document the narrowed scope so operators know what changed.

## Other Differences Noted (Informational)

- Public API now exports `TaskiqRunLauncher` via `dagster_taskiq.__all__` (`dagster_taskiq/__init__.py:3`), whereas Celery kept the launcher internal.
- Executor/launcher configuration is AWS-specific (`queue_url`, `region_name`, `endpoint_url`) instead of Celery's generic `broker`/`backend`/`include`.
- `app.py` eagerly starts the broker and result backend in a fresh event loop on import, unlike Celery's lazy app creation; ensure this behaviour is desired for worker processes.
