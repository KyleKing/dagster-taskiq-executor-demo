"""Entry point for running the TaskIQ worker inside the container."""

from __future__ import annotations

from taskiq.cli.common_args import LogLevel
from taskiq.cli.worker.args import WorkerArgs
from taskiq.cli.worker.run import run_worker

from .config import get_settings
from .logging import configure_logging, get_logger


def main() -> None:
    """Configure logging and start the TaskIQ worker.

    Raises:
        SystemExit: If the worker fails to start.

    """
    settings = get_settings()
    configure_logging()
    logger = get_logger(__name__)

    log_level = _to_log_level(settings.log_level)
    args = WorkerArgs(
        broker="taskiq_demo.tasks:broker",
        modules=["taskiq_demo.tasks"],
        configure_logging=False,
        log_level=log_level,
        workers=settings.worker_processes,
        max_async_tasks=settings.worker_max_async_tasks,
        max_prefetch=settings.worker_max_prefetch,
    )

    status = run_worker(args)
    if status:
        logger.error("worker.exit", status=status)
        raise SystemExit(status)


def _to_log_level(level: str) -> LogLevel:
    """Map configuration string to TaskIQ LogLevel enum.

    Args:
        level: The log level string.

    Returns:
        The TaskIQ LogLevel enum value.

    Raises:
        ValueError: If the log level is unsupported.

    """
    try:
        return LogLevel[level.upper()]
    except KeyError as exc:
        msg = f"Unsupported log level '{level}'."
        raise ValueError(msg) from exc


if __name__ == "__main__":
    main()
