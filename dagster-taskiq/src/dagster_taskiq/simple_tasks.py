"""Simplified task definitions using Dagster's built-in execution APIs.

This module provides simplified task definitions that execute entire Dagster jobs
as single tasks, using Dagster's internal command body functions rather than
custom orchestration logic.

Key Simplifications:
- Uses _execute_run_command_body() for job execution (same as dagster-celery)
- Executes entire job as one task (no step-level parallelism across workers)
- Simpler than custom orchestration loop
- Leverages TaskIQ's native result handling

Trade-offs:
- No step-level distribution (all steps execute in one worker)
- May be slower for jobs with many parallelizable steps
- Simpler and more maintainable
- Better for jobs with few steps or sequential dependencies
"""

import logging
from typing import Any

from dagster import DagsterInstance
from dagster._cli.api import (
    _execute_run_command_body,
    _resume_run_command_body,
)
from dagster._grpc.types import ExecuteRunArgs, ResumeRunArgs
from dagster._serdes import unpack_value
from dagster_shared.serdes.serdes import JsonSerializableValue
from taskiq import AsyncBroker

logger = logging.getLogger(__name__)


def _send_to_null(_event: Any) -> None:
    """Null event sink for Dagster output.

    The execute_run_command_body writes events to a stream. Since we're
    running in a TaskIQ worker, we don't need to capture this output.
    """


def register_simple_tasks(broker: AsyncBroker) -> None:
    """Register simplified Dagster tasks with the broker.

    This function registers TaskIQ tasks that execute entire Dagster jobs
    using Dagster's built-in execution functions.

    Args:
        broker: The TaskIQ broker to register tasks with

    Example:
        >>> from dagster_taskiq.simple_broker import make_simple_broker
        >>> broker = make_simple_broker()
        >>> register_simple_tasks(broker)
        >>> # Broker now has dagster_execute_job task registered
    """

    @broker.task(name="dagster_execute_job", labels={"component": "dagster"})
    def execute_job(execute_job_args_packed: JsonSerializableValue) -> int:
        """Execute a complete Dagster job as a single task.

        This task executes an entire Dagster job using Dagster's internal
        _execute_run_command_body function, which is the same function used
        by dagster-celery and the Dagster CLI.

        Args:
            execute_job_args_packed: Serialized ExecuteRunArgs containing:
                - run_id: The Dagster run ID to execute
                - instance_ref: Dagster instance reference
                - set_exit_code_on_failure: Whether to return non-zero on failure

        Returns:
            Exit code (0 for success, non-zero for failure)

        Note:
            All steps execute sequentially in a single worker. Dagster's internal
            threading/multiprocessing may still provide some parallelism within
            the worker process, but steps are not distributed across workers.
        """
        # Deserialize job arguments
        args: ExecuteRunArgs = unpack_value(
            val=execute_job_args_packed,
            as_type=ExecuteRunArgs,
        )

        # Get Dagster instance using DagsterInstance.get() which respects
        # DAGSTER_HOME and other environment variables
        with DagsterInstance.get() as instance:
            # Execute the run using Dagster's internal API
            # This is the same function used by dagster-celery
            exit_code = _execute_run_command_body(
                instance=instance,
                run_id=args.run_id,  # Use the provided run_id, don't generate new one
                write_stream_fn=_send_to_null,  # Discard output stream
                set_exit_code_on_failure=(
                    args.set_exit_code_on_failure
                    if args.set_exit_code_on_failure is not None
                    else True
                ),
            )

            logger.info(
                "Dagster job execution completed: run_id=%s, exit_code=%s",
                args.run_id,
                exit_code,
            )

            return exit_code

    @broker.task(name="dagster_resume_job", labels={"component": "dagster"})
    def resume_job(resume_job_args_packed: JsonSerializableValue) -> int:
        """Resume a Dagster job after interruption.

        Args:
            resume_job_args_packed: Serialized ResumeRunArgs

        Returns:
            Exit code (0 for success)
        """
        args: ResumeRunArgs = unpack_value(
            val=resume_job_args_packed,
            as_type=ResumeRunArgs,
        )

        with DagsterInstance.get() as instance:
            exit_code = _resume_run_command_body(
                instance=instance,
                run_id=args.run_id,
                write_stream_fn=_send_to_null,
                set_exit_code_on_failure=(
                    args.set_exit_code_on_failure
                    if args.set_exit_code_on_failure is not None
                    else True
                ),
            )

            logger.info(
                "Dagster job resume completed: run_id=%s, exit_code=%s",
                args.run_id,
                exit_code,
            )

            return exit_code

    # Store references for later retrieval
    # Using a more robust pattern than private attributes
    if not hasattr(broker, "_dagster_tasks"):
        broker._dagster_tasks = {}  # type: ignore[attr-defined]

    broker._dagster_tasks["execute_job"] = execute_job  # type: ignore[attr-defined]
    broker._dagster_tasks["resume_job"] = resume_job  # type: ignore[attr-defined]


def get_execute_job_task(broker: AsyncBroker) -> Any:
    """Get the registered execute_job task from the broker.

    Args:
        broker: The broker with registered tasks

    Returns:
        The execute_job task function

    Raises:
        AttributeError: If tasks haven't been registered yet

    Example:
        >>> task = get_execute_job_task(broker)
        >>> await task.kiq(job_args)
    """
    if not hasattr(broker, "_dagster_tasks") or "execute_job" not in broker._dagster_tasks:  # type: ignore[attr-defined]
        msg = "Tasks not registered. Call register_simple_tasks() first."
        raise AttributeError(msg)

    return broker._dagster_tasks["execute_job"]  # type: ignore[attr-defined]


def get_resume_job_task(broker: AsyncBroker) -> Any:
    """Get the registered resume_job task from the broker.

    Args:
        broker: The broker with registered tasks

    Returns:
        The resume_job task function

    Raises:
        AttributeError: If tasks haven't been registered yet
    """
    if not hasattr(broker, "_dagster_tasks") or "resume_job" not in broker._dagster_tasks:  # type: ignore[attr-defined]
        msg = "Tasks not registered. Call register_simple_tasks() first."
        raise AttributeError(msg)

    return broker._dagster_tasks["resume_job"]  # type: ignore[attr-defined]


def create_simple_tasks(broker: AsyncBroker) -> dict[str, Any]:
    """Create and register simplified Dagster tasks.

    This is a convenience function that registers tasks and returns
    a dictionary of task references for easy access.

    Args:
        broker: The TaskIQ broker

    Returns:
        Dictionary mapping task names to task functions

    Example:
        >>> tasks = create_simple_tasks(broker)
        >>> await tasks["execute_job"].kiq(job_args)
    """
    register_simple_tasks(broker)

    return {
        "execute_job": get_execute_job_task(broker),
        "resume_job": get_resume_job_task(broker),
    }


def create_labeled_job_task(broker: AsyncBroker, job_name: str, run_id: str) -> Any:
    """Helper to create a job task with Dagster-specific labels.

    These labels are used by middleware for logging and metrics.

    Args:
        broker: The TaskIQ broker
        job_name: Name of the Dagster job
        run_id: Dagster run ID

    Returns:
        Task kicker with labels attached

    Example:
        >>> task = create_labeled_job_task(broker, "my_job", "run-123")
        >>> await task.kiq(job_args)
        >>> # Middleware will see job_name and run_id in labels
    """
    if not hasattr(broker, "_dagster_tasks") or "execute_job" not in broker._dagster_tasks:  # type: ignore[attr-defined]
        register_simple_tasks(broker)

    execute_task = get_execute_job_task(broker)

    # Create kicker with Dagster-specific labels
    return execute_task.kicker().with_labels(
        job_name=job_name,
        run_id=run_id,
        component="dagster",
        execution_mode="simple",
    )
