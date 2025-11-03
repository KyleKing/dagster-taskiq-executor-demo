# Dagster TaskIQ vs Dagster Celery Parity Review

## Findings (Action Required)

- **Queue routing tags ignored (High)** – `DAGSTER_TASKIQ_QUEUE_TAG` on steps/runs and the launcher's `default_queue` are never used when calling `task.kiq(...)`, so every task goes to the single broker queue regardless of tags (`dagster_taskiq/core_execution_loop.py:137`, `dagster_taskiq/executor.py:102`, `dagster_taskiq/launcher.py:200`). Restore routing behaviour by mapping Dagster tags to SQS queue selection (per-run and per-step).
- **Priority inversion via SQS delay (High)** – `_get_step_priority` defaults to 5 and the executor multiplies this value by 10 to set a `delay` label, forcing new tasks to sit ~50 s before being visible; higher priority yields *longer* wait times (`dagster_taskiq/executor.py:128`). Replace the delay logic with a priority mapping that keeps higher priority steps running sooner (e.g. FIFO priorities, per-queue ordering, or TaskIQ result backend priority features).
- **`config_source` dropped (Medium)** – Executor/launcher wrap user `config_source`, but `make_app` ignores it and hard-codes SQS/S3 settings (`dagster_taskiq/executor.py:151`, `dagster_taskiq/launcher.py:76`, `dagster_taskiq/make_app.py:37`). Thread `config_source` (and `DEFAULT_CONFIG` values) through to broker creation or clearly remove the option.
- **Run termination unsupported (Medium)** – Celery revoked tasks via `AsyncResult.revoke`; TaskIQ now logs “not supported” and returns `False` (`dagster_taskiq/launcher.py:124`). Implement termination (e.g. by sending cancel messages via `CancellableSQSBroker`) or document the limitation and adjust `supports_resume_run`/`terminate` expectations.
- **Worker health check regressed (Medium)** – Launcher still advertises `supports_check_run_worker_health = True`, but always returns `WorkerStatus.UNKNOWN` because no result backend status is read (`dagster_taskiq/launcher.py:248`). Either integrate TaskIQ result backend status or flip the capability flag to `False`.

## Next Steps

1. Implement queue selection parity: honour run/step tags when building SQS queue names and ensure executors/launchers submit to user-selected queues.
1. Rework priority handling to avoid using message delay as a proxy; align with Celery behaviour or introduce an alternative that preserves higher-priority execution ordering.
1. Decide how `config_source` should work with TaskIQ. If configurable knobs exist, pass them through; if not, remove the field from schemas to avoid misleading users.
1. Design a termination path (leveraging `CancellableSQSBroker`/`CancellableReceiver`) or explicitly mark termination unsupported in both code and docs.
1. Update `supports_check_run_worker_health` to reflect real capabilities; add backend polling if feasible so health checks return SUCCESS/FAILED/RUNNING like Celery.
1. Audit CLI parity: reintroduce equivalents for `worker terminate/status` or document the narrowed scope so operators know what changed.

## Other Differences Noted (Informational)

- Public API now exports `TaskiqRunLauncher` via `dagster_taskiq.__all__` (`dagster_taskiq/__init__.py:3`), whereas Celery kept the launcher internal.
- Executor/launcher configuration is AWS-specific (`queue_url`, `region_name`, `endpoint_url`) instead of Celery’s generic `broker`/`backend`/`include`.
- `app.py` eagerly starts the broker and result backend in a fresh event loop on import, unlike Celery’s lazy app creation; ensure this behaviour is desired for worker processes.
