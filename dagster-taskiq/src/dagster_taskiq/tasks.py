"""Task definitions for Taskiq workers.

This module defines the Taskiq tasks that execute Dagster runs and steps
on worker processes.
"""

from typing import Any

from dagster import DagsterInstance
from dagster import _check as check  # noqa: PLC2701
from dagster._cli.api import (  # pyright: ignore[reportPrivateUsage]
    _execute_run_command_body,  # noqa: PLC2701  # pyright: ignore[reportPrivateUsage]
    _resume_run_command_body,  # noqa: PLC2701  # pyright: ignore[reportPrivateUsage]
)
from dagster._core.definitions.reconstruct import ReconstructableJob  # noqa: PLC2701
from dagster._core.events import EngineEventData  # noqa: PLC2701
from dagster._core.execution.api import create_execution_plan, execute_plan_iterator  # noqa: PLC2701
from dagster._grpc.types import ExecuteRunArgs, ExecuteStepArgs, ResumeRunArgs  # noqa: PLC2701
from dagster._serdes import serialize_value, unpack_value  # noqa: PLC2701
from dagster_shared.serdes.serdes import JsonSerializableValue
from taskiq import AsyncBroker

from dagster_taskiq.config import (
    TASK_EXECUTE_JOB_NAME,
    TASK_EXECUTE_PLAN_NAME,
    TASK_RESUME_JOB_NAME,
)
from dagster_taskiq.core_execution_loop import DELEGATE_MARKER


def create_task(broker: AsyncBroker, **task_kwargs: Any) -> Any:
    """Create the execute_plan task for taskiq.

    Args:
        broker: The taskiq broker
        **task_kwargs: Additional task keyword arguments

    Returns:
        The execute_plan task function
    """

    @broker.task(task_name=TASK_EXECUTE_PLAN_NAME, **task_kwargs)
    def _execute_plan(
        execute_step_args_packed: dict[str, Any],
        executable_dict: dict[str, Any],
    ) -> list[Any]:
        """Execute a plan step in a taskiq worker.

        Args:
            execute_step_args_packed: Serialized ExecuteStepArgs
            executable_dict: Serialized ReconstructableJob

        Returns:
            List of serialized DagsterEvent objects
        """
        execute_step_args = unpack_value(
            check.dict_param(
                execute_step_args_packed,
                "execute_step_args_packed",
            ),
            as_type=ExecuteStepArgs,
        )

        check.dict_param(executable_dict, "executable_dict")

        instance = DagsterInstance.from_ref(execute_step_args.instance_ref)  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]

        recon_job = ReconstructableJob.from_dict(executable_dict)
        retry_mode = execute_step_args.retry_mode

        dagster_run = instance.get_run_by_id(execute_step_args.run_id)
        check.invariant(dagster_run, f"Could not load run {execute_step_args.run_id}")

        step_keys_str = ", ".join(execute_step_args.step_keys_to_execute or [])

        execution_plan = create_execution_plan(
            recon_job,
            dagster_run.run_config,  # type: ignore[union-attr]  # pyright: ignore[reportOptionalMemberAccess]
            step_keys_to_execute=execute_step_args.step_keys_to_execute,
            known_state=execute_step_args.known_state,
        )

        # Get worker/task context info for reporting
        # Taskiq doesn't provide the same context as Celery, so we'll use a placeholder
        worker_name = "taskiq-worker"

        step_handle = execution_plan.step_handle_for_single_step_plans()
        # Lazy import to avoid circular dependency
        from dagster_taskiq.executor import TaskiqExecutor  # noqa: PLC0415

        engine_event = instance.report_engine_event(
            f"Executing steps {step_keys_str} in taskiq worker",
            dagster_run,
            EngineEventData(
                {
                    "step_keys": step_keys_str,
                    "Taskiq worker": worker_name,
                },
                marker_end=DELEGATE_MARKER,
            ),
            TaskiqExecutor,
            step_key=step_handle.to_key() if step_handle else None,  # pyright: ignore[reportOptionalMemberAccess]
        )

        events = [engine_event]
        for step_event in execute_plan_iterator(
            execution_plan=execution_plan,
            job=recon_job,
            dagster_run=dagster_run,  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
            instance=instance,
            retry_mode=retry_mode,
            run_config=dagster_run.run_config if dagster_run else {},  # pyright: ignore[reportOptionalMemberAccess]
        ):
            events.append(step_event)  # noqa: PERF402

        return [serialize_value(event) for event in events]

    return _execute_plan


def _send_to_null(_event: Any) -> None:
    """Null event sink."""


def create_execute_job_task(broker: AsyncBroker, **task_kwargs: Any) -> Any:
    """Create a Taskiq task that executes a run and registers status updates with the Dagster instance.

    Args:
        broker: The taskiq broker
        **task_kwargs: Additional task keyword arguments

    Returns:
        The execute_job task function
    """

    @broker.task(task_name=TASK_EXECUTE_JOB_NAME, **task_kwargs)
    def _execute_job(execute_job_args_packed: JsonSerializableValue) -> int:
        """Execute a full Dagster job run.

        Args:
            execute_job_args_packed: Serialized ExecuteRunArgs

        Returns:
            Exit code (0 for success)
        """
        args: ExecuteRunArgs = unpack_value(
            val=execute_job_args_packed,
            as_type=ExecuteRunArgs,
        )

        with DagsterInstance.get() as instance:
            return _execute_run_command_body(
                instance=instance,
                run_id=args.run_id,
                write_stream_fn=_send_to_null,
                set_exit_code_on_failure=(
                    args.set_exit_code_on_failure if args.set_exit_code_on_failure is not None else True
                ),
            )

    return _execute_job


def create_resume_job_task(broker: AsyncBroker, **task_kwargs: Any) -> Any:
    """Create a Taskiq task that resumes a run and registers status updates with the Dagster instance.

    Args:
        broker: The taskiq broker
        **task_kwargs: Additional task keyword arguments

    Returns:
        The resume_job task function
    """

    @broker.task(task_name=TASK_RESUME_JOB_NAME, **task_kwargs)
    def _resume_job(resume_job_args_packed: JsonSerializableValue) -> int:
        """Resume a Dagster job run.

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
            return _resume_run_command_body(
                instance=instance,
                run_id=args.run_id,
                write_stream_fn=_send_to_null,
                set_exit_code_on_failure=(
                    args.set_exit_code_on_failure if args.set_exit_code_on_failure is not None else True
                ),
            )

    return _resume_job
