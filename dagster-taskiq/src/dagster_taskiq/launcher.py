"""Taskiq run launcher for Dagster.

This module provides TaskiqRunLauncher which launches Dagster runs as Taskiq tasks
on AWS SQS.
"""

import asyncio
import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self

from dagster import (
    DagsterInstance,
    DagsterRun,
    Field,
    Noneable,
    Permissive,
    StringSource,
)
from dagster import (
    _check as check,  # noqa: PLC2701
)
from dagster._core.events import EngineEventData  # noqa: PLC2701
from dagster._core.launcher import (
    CheckRunHealthResult,  # noqa: PLC2701
    LaunchRunContext,
    ResumeRunContext,
    RunLauncher,  # noqa: PLC2701
    WorkerStatus,  # noqa: PLC2701
)
from dagster._grpc.types import ExecuteRunArgs, ResumeRunArgs  # noqa: PLC2701
from dagster._serdes import ConfigurableClass, ConfigurableClassData, pack_value  # noqa: PLC2701
from taskiq import AsyncBroker
from typing_extensions import override

from dagster_taskiq.config import DEFAULT_CONFIG, TASK_EXECUTE_JOB_NAME, TASK_RESUME_JOB_NAME
from dagster_taskiq.defaults import aws_region_name, sqs_queue_url
from dagster_taskiq.make_app import make_app
from dagster_taskiq.tags import DAGSTER_TASKIQ_TASK_ID_TAG
from dagster_taskiq.tasks import create_execute_job_task, create_resume_job_task

if TYPE_CHECKING:
    from dagster._config import UserConfigSchema


class TaskiqRunLauncher(RunLauncher, ConfigurableClass):
    """Dagster Run Launcher which starts runs as Taskiq tasks on AWS SQS.

    This launcher submits full Dagster runs as Taskiq tasks, which are distributed
    via AWS SQS to worker processes.
    """

    _instance: DagsterInstance  # pyright: ignore[reportIncompatibleMethodOverride]
    broker: AsyncBroker

    def __init__(
        self,
        queue_url: str | None = None,
        region_name: str | None = None,
        endpoint_url: str | None = None,
        config_source: dict[str, Any] | None = None,
        inst_data: ConfigurableClassData | None = None,
    ) -> None:
        """Initialize the Taskiq run launcher.

        Args:
            queue_url: SQS queue URL
            region_name: AWS region name
            endpoint_url: Custom AWS endpoint (for LocalStack)
            config_source: Additional configuration
            inst_data: Configurable class data
        """
        self._inst_data = check.opt_inst_param(inst_data, "inst_data", ConfigurableClassData)

        self.queue_url = check.opt_str_param(queue_url, "queue_url", default=sqs_queue_url)
        self.region_name = check.opt_str_param(region_name, "region_name", default=aws_region_name)
        self.endpoint_url = check.opt_str_param(endpoint_url, "endpoint_url")
        self.config_source = dict(DEFAULT_CONFIG, **check.opt_dict_param(config_source, "config_source"))

        # Create the Taskiq broker
        self.broker = make_app(app_args=self.app_args())
        self._supports_cancellation = callable(getattr(self.broker, "cancel_task", None))

        super().__init__()

    def app_args(self) -> dict[str, Any]:
        """Get arguments for broker creation.

        Returns:
            Dictionary of broker configuration
        """
        return {
            "queue_url": self.queue_url,
            "region_name": self.region_name,
            "endpoint_url": self.endpoint_url,
            "config_source": self.config_source,
        }

    def launch_run(self, context: LaunchRunContext) -> None:
        """Launch a Dagster run as a Taskiq task.

        Args:
            context: Launch context containing the run to launch
        """
        run = context.dagster_run
        job_origin = check.not_none(run.job_code_origin)

        args = ExecuteRunArgs(
            job_origin=job_origin,
            run_id=run.run_id,
            instance_ref=self._instance.get_ref(),
            set_exit_code_on_failure=True,
        )

        task = create_execute_job_task(self.broker)

        self._launch_taskiq_task_run(
            run=run,
            task=task,
            task_args={"execute_job_args_packed": pack_value(args)},
            routing_key=TASK_EXECUTE_JOB_NAME,
        )

    def terminate(self, run_id: str) -> bool:  # noqa: PLR0911
        """Terminate a running task.

        Args:
            run_id: ID of the run to terminate

        Returns:
            True if a cancellation request was issued, False otherwise.
        """
        run = self._instance.get_run_by_id(run_id)
        if run is None:
            return False

        task_id = run.tags.get(DAGSTER_TASKIQ_TASK_ID_TAG)
        if not task_id:
            self._instance.report_engine_event(
                "Taskiq task ID missing; unable to cancel run task.",
                run,
                cls=self.__class__,
            )
            return False

        if not self._supports_cancellation:
            self._instance.report_engine_event(
                "Taskiq broker does not support task cancellation.",
                run,
                cls=self.__class__,
            )
            return False

        cancel_callable = getattr(self.broker, "cancel_task", None)
        if not callable(cancel_callable):
            self._instance.report_engine_event(
                "Taskiq broker does not expose cancel_task; unable to cancel.",
                run,
                cls=self.__class__,
            )
            return False

        try:
            task_uuid = uuid.UUID(str(task_id))
        except (TypeError, ValueError):
            self._instance.report_engine_event(
                f"Invalid Taskiq task ID ({task_id}); cannot cancel run task.",
                run,
                cls=self.__class__,
            )
            return False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.broker.startup())
            loop.run_until_complete(cancel_callable(task_uuid))  # pyright: ignore[reportArgumentType]
        except Exception as exc:
            self._instance.report_engine_event(
                f"Failed to submit Taskiq cancellation request: {exc}",
                run,
                cls=self.__class__,
            )
            return False
        finally:
            loop.close()

        self._instance.report_engine_event(
            "Requested Taskiq task cancellation.",
            run,
            EngineEventData.interrupted([task_id]),
            cls=self.__class__,
        )
        return True

    @property
    def supports_resume_run(self) -> bool:
        """Whether this launcher supports resuming runs.

        Returns:
            True
        """
        return True

    def resume_run(self, context: ResumeRunContext) -> None:
        """Resume a Dagster run as a Taskiq task.

        Args:
            context: Resume context containing the run to resume
        """
        run = context.dagster_run
        job_origin = check.not_none(run.job_code_origin)

        args = ResumeRunArgs(
            job_origin=job_origin,
            run_id=run.run_id,
            instance_ref=self._instance.get_ref(),
            set_exit_code_on_failure=True,
        )

        task = create_resume_job_task(self.broker)

        self._launch_taskiq_task_run(
            run=run,
            task=task,
            task_args={"resume_job_args_packed": pack_value(args)},
            routing_key=TASK_RESUME_JOB_NAME,
        )

    def _launch_taskiq_task_run(
        self,
        run: DagsterRun,
        task: Any,
        task_args: dict[str, Any],
        routing_key: str,
    ) -> None:
        """Launch a Taskiq task for the run.

        Args:
            run: The Dagster run
            task: The Taskiq task function
            task_args: Arguments to pass to the task
            routing_key: Task routing identifier
        """
        self._instance.report_engine_event(
            "Creating Taskiq run worker job task",
            run,
            cls=self.__class__,
        )

        # Submit task asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.broker.startup())
            if hasattr(self.broker, "result_backend") and self.broker.result_backend:  # type: ignore[truthy-bool]
                loop.run_until_complete(self.broker.result_backend.startup())

            # Use kiq() to submit the task with labels
            result = loop.run_until_complete(
                task.kiq(
                    **task_args,
                    labels={
                        "routing_key": routing_key,
                    },
                )
            )

            # Store the task ID for tracking
            task_id = result.task_id if hasattr(result, "task_id") else str(id(result))

            self._instance.add_run_tags(
                run.run_id,
                {DAGSTER_TASKIQ_TASK_ID_TAG: task_id},
            )

            self._instance.report_engine_event(
                "Taskiq task has been forwarded to SQS.",
                run,
                EngineEventData({
                    "Run ID": run.run_id,
                    "Taskiq Task ID": task_id,
                }),
                cls=self.__class__,
            )
        finally:
            loop.close()

    @property
    def supports_check_run_worker_health(self) -> bool:
        """Whether this launcher supports checking worker health.

        Returns:
            True
        """
        return True

    def _check_result_backend_health(self, task_id: str) -> CheckRunHealthResult:
        """Check task health using the result backend.

        Args:
            task_id: The task ID to check

        Returns:
            Health check result with worker status
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.broker.startup())
            if hasattr(self.broker.result_backend, "startup"):  # type: ignore[attr-defined]
                loop.run_until_complete(self.broker.result_backend.startup())  # type: ignore[attr-defined]

            # Check if result is ready
            result_backend = self.broker.result_backend  # type: ignore[assignment]
            is_ready = loop.run_until_complete(result_backend.is_result_ready(task_id))  # type: ignore[attr-defined]

            if not is_ready:
                return CheckRunHealthResult(WorkerStatus.RUNNING, f"Task {task_id} is running")

            # Result is ready, check if it's an error
            try:
                result = loop.run_until_complete(result_backend.get_result(task_id))  # type: ignore[attr-defined]
                if hasattr(result, "is_err") and result.is_err:  # type: ignore[attr-defined]
                    return CheckRunHealthResult(WorkerStatus.FAILED, f"Task {task_id} failed")
                return CheckRunHealthResult(WorkerStatus.SUCCESS, f"Task {task_id} completed")
            except Exception:
                # Result exists but couldn't be retrieved - assume it's processing
                return CheckRunHealthResult(WorkerStatus.RUNNING, f"Task {task_id} result available")
        finally:
            loop.close()

    def check_run_worker_health(self, run: DagsterRun) -> CheckRunHealthResult:
        """Check the health status of a running task using the result backend.

        Args:
            run: The Dagster run to check

        Returns:
            Health check result with worker status
        """
        if DAGSTER_TASKIQ_TASK_ID_TAG not in run.tags:
            return CheckRunHealthResult(WorkerStatus.UNKNOWN, "No task ID found for run")

        task_id = run.tags[DAGSTER_TASKIQ_TASK_ID_TAG]

        # Check result backend if available
        if not (hasattr(self.broker, "result_backend") and self.broker.result_backend):  # type: ignore[truthy-bool]
            return CheckRunHealthResult(
                WorkerStatus.UNKNOWN, f"Task {task_id} status cannot be determined without result backend"
            )

        try:
            return self._check_result_backend_health(task_id)
        except Exception as e:
            # If we can't check the backend, return UNKNOWN
            return CheckRunHealthResult(
                WorkerStatus.UNKNOWN, f"Could not check result backend for task {task_id}: {e}"
            )

    @override
    def get_run_worker_debug_info(self, run: DagsterRun, include_container_logs: bool | None = True) -> str | None:
        """Get debug information about the worker running this task.

        Args:
            run: The Dagster run
            include_container_logs: Whether to include container logs (unused)

        Returns:
            Debug information as a string
        """
        if DAGSTER_TASKIQ_TASK_ID_TAG not in run.tags:
            return "No task ID found for run"

        task_id = run.tags[DAGSTER_TASKIQ_TASK_ID_TAG]

        return str({
            "run_id": run.run_id,
            "taskiq_task_id": task_id,
            "queue_url": self.queue_url,
            "region": self.region_name,
        })

    @property
    def inst_data(self) -> ConfigurableClassData | None:
        """Get the instance data.

        Returns:
            ConfigurableClassData instance
        """
        return self._inst_data

    @classmethod
    def config_type(cls) -> "UserConfigSchema":
        """Get the configuration schema for this launcher.

        Returns:
            Configuration schema dictionary
        """
        return {
            "queue_url": Field(
                Noneable(StringSource),
                is_required=False,
                description=("The URL of the SQS queue. Default: environment variable DAGSTER_TASKIQ_SQS_QUEUE_URL."),
            ),
            "region_name": Field(
                Noneable(StringSource),
                is_required=False,
                description=("AWS region name. Default: environment variable AWS_DEFAULT_REGION or us-east-1."),
            ),
            "endpoint_url": Field(
                Noneable(StringSource),
                is_required=False,
                description="Custom AWS endpoint URL (for LocalStack). Default: None.",
            ),
            "config_source": Field(
                Noneable(Permissive()),
                is_required=False,
                description="Additional settings for the Taskiq broker.",
            ),
        }

    @classmethod
    def from_config_value(cls, inst_data: ConfigurableClassData, config_value: Mapping[str, Any]) -> Self:
        """Create a launcher instance from configuration.

        Args:
            inst_data: Instance data
            config_value: Configuration values

        Returns:
            TaskiqRunLauncher instance
        """
        return cls(inst_data=inst_data, **config_value)
