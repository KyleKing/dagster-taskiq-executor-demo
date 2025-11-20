"""Simplified task definitions using TaskIQ's native features.

This module provides simplified task definitions that execute entire Dagster jobs
as single tasks, rather than orchestrating individual steps. This trades some
parallelism for significant code simplification.

Key Differences from Full Implementation:
- Executes entire job as one task (no step-level parallelism)
- Uses Dagster's execute_in_process() for internal orchestration
- Leverages TaskIQ's native result handling
- No custom polling loops needed
"""

from typing import Any

from dagster import DagsterInstance
from dagster._core.execution.api import execute_in_process
from dagster._core.definitions.reconstruct import ReconstructableJob
from dagster._grpc.types import ExecuteRunArgs
from dagster._serdes import serialize_value, unpack_value
from dagster_shared.serdes import JsonSerializableValue
from taskiq import AsyncBroker


def register_simple_tasks(broker: AsyncBroker) -> None:
    """Register simplified Dagster tasks with the broker.

    This function registers TaskIQ tasks that execute entire Dagster jobs,
    using Dagster's built-in orchestration rather than custom step coordination.

    Args:
        broker: The TaskIQ broker to register tasks with

    Example:
        >>> from dagster_taskiq.simple_broker import make_simple_broker
        >>> broker = make_simple_broker()
        >>> register_simple_tasks(broker)
        >>> # Broker now has dagster_execute_job task registered
    """

    @broker.task(name="dagster_execute_job", labels={"component": "dagster"})
    async def execute_job(execute_job_args_packed: JsonSerializableValue) -> JsonSerializableValue:
        """Execute a complete Dagster job as a single task.

        This task executes an entire Dagster job using execute_in_process(),
        which handles step-level orchestration internally. This is simpler than
        the full implementation but doesn't provide step-level parallelism across
        workers.

        Args:
            execute_job_args_packed: Serialized ExecuteRunArgs containing:
                - run_id: The Dagster run ID
                - job: The reconstructable job definition
                - run_config: Job configuration
                - instance_ref: Dagster instance reference

        Returns:
            Serialized list of DagsterEvent objects from the execution

        Note:
            All steps execute sequentially in a single worker. Dagster's internal
            threading/multiprocessing may still provide some parallelism within
            the worker process.
        """
        # Deserialize job arguments
        args: ExecuteRunArgs = unpack_value(
            val=execute_job_args_packed,
            as_type=ExecuteRunArgs,
        )

        # Get Dagster instance
        with DagsterInstance.from_ref(args.instance_ref) as instance:
            # Reconstruct the job
            job = ReconstructableJob.from_dict(args.job_dict) if hasattr(args, "job_dict") else args.job

            # Execute the entire job using Dagster's built-in orchestration
            # This handles step dependencies, parallelism (via threads/processes),
            # and event streaming internally
            result = execute_in_process(
                job=job,
                instance=instance,
                run_config=args.run_config,
                raise_on_error=False,  # Return errors in result rather than raising
            )

            # Serialize all events from the execution
            events = list(result.all_events) if hasattr(result, "all_events") else []
            return serialize_value(events)

    # Store reference for later use
    broker._dagster_execute_job_task = execute_job  # type: ignore[attr-defined]


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
    if not hasattr(broker, "_dagster_execute_job_task"):
        msg = "Tasks not registered. Call register_simple_tasks() first."
        raise AttributeError(msg)

    return broker._dagster_execute_job_task  # type: ignore[attr-defined]


# Simplified task registration pattern - no factory functions needed
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
    }


# Example of how to use with middleware for labels
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
    if not hasattr(broker, "_dagster_execute_job_task"):
        register_simple_tasks(broker)

    execute_task = get_execute_job_task(broker)

    # Create kicker with Dagster-specific labels
    return execute_task.kicker().with_labels(
        job_name=job_name,
        run_id=run_id,
        component="dagster",
        execution_mode="simple",
    )
