"""TaskIQ middleware for Dagster observability.

This module provides TaskIQ middleware components that handle cross-cutting concerns
like logging, metrics, and error reporting. This is the TaskIQ-native approach to
observability rather than scattering logging throughout custom code.
"""

import logging
from typing import Any

from taskiq import TaskiqMessage, TaskiqResult
from taskiq.abc.middleware import TaskiqMiddleware

logger = logging.getLogger(__name__)


class DagsterLoggingMiddleware(TaskiqMiddleware):
    """Middleware for logging Dagster task execution.

    This middleware logs task lifecycle events using TaskIQ's native hooks,
    providing observability without custom code in the execution loop.

    Logged Events:
        - Task start (pre_execute)
        - Task completion (post_save)
        - Task errors (post_save with is_err)

    Example:
        >>> from taskiq import AsyncBroker
        >>> broker = AsyncBroker(...)
        >>> broker.add_middlewares(DagsterLoggingMiddleware())
    """

    async def startup(self) -> None:
        """Initialize middleware when broker starts."""
        logger.info("DagsterLoggingMiddleware initialized")

    async def shutdown(self) -> None:
        """Cleanup when broker shuts down."""
        logger.info("DagsterLoggingMiddleware shutting down")

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        """Log before task execution.

        Args:
            message: The task message about to be executed

        Returns:
            The unmodified message (logging is observability only)
        """
        task_name = message.task_name
        task_id = message.task_id

        # Extract Dagster-specific labels if available
        run_id = message.labels.get("run_id")
        step_key = message.labels.get("step_key")
        job_name = message.labels.get("job_name")

        # Log with structured data
        extra_info = {
            "task_name": task_name,
            "task_id": str(task_id),
            "run_id": run_id,
            "step_key": step_key,
            "job_name": job_name,
        }

        if step_key:
            logger.info(
                f"Executing Dagster step: {step_key} (run_id={run_id})",
                extra=extra_info,
            )
        elif job_name:
            logger.info(
                f"Executing Dagster job: {job_name} (run_id={run_id})",
                extra=extra_info,
            )
        else:
            logger.info(
                f"Executing task: {task_name} (task_id={task_id})",
                extra=extra_info,
            )

        return message

    async def post_save(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
    ) -> None:
        """Log after task execution and result storage.

        Args:
            message: The task message that was executed
            result: The task result
        """
        task_name = message.task_name
        task_id = message.task_id
        step_key = message.labels.get("step_key")
        run_id = message.labels.get("run_id")

        extra_info = {
            "task_name": task_name,
            "task_id": str(task_id),
            "run_id": run_id,
            "step_key": step_key,
            "is_error": result.is_err,
        }

        if result.is_err:
            # Task failed
            error_info = result.error if hasattr(result, "error") else "Unknown error"
            if step_key:
                logger.error(
                    f"Dagster step failed: {step_key} - {error_info}",
                    extra=extra_info,
                )
            else:
                logger.error(
                    f"Task failed: {task_name} - {error_info}",
                    extra=extra_info,
                )
        else:
            # Task succeeded
            if step_key:
                logger.info(
                    f"Dagster step completed: {step_key}",
                    extra=extra_info,
                )
            else:
                logger.info(
                    f"Task completed: {task_name}",
                    extra=extra_info,
                )


class DagsterMetricsMiddleware(TaskiqMiddleware):
    """Middleware for collecting execution metrics (future implementation).

    This middleware would collect metrics like:
    - Task execution duration
    - Success/failure rates
    - Queue depth
    - Worker utilization

    Could integrate with CloudWatch, Prometheus, or other metrics systems.

    Example:
        >>> broker.add_middlewares(DagsterMetricsMiddleware(
        ...     metrics_backend="cloudwatch"
        ... ))
    """

    def __init__(self, metrics_backend: str = "cloudwatch") -> None:
        """Initialize metrics middleware.

        Args:
            metrics_backend: Which metrics system to use
        """
        super().__init__()
        self.metrics_backend = metrics_backend
        logger.info(f"Metrics middleware configured with backend: {metrics_backend}")

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        """Record task start time."""
        # Future: Start timing
        return message

    async def post_save(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
    ) -> None:
        """Record task completion and metrics."""
        # Future: Record duration, success/failure
        pass
