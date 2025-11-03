import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Optional

from dagster import (
    DagsterInstance,
    DagsterRun,
    Field,
    Noneable,
    Permissive,
    StringSource,
    _check as check,
)
from dagster._core.events import EngineEventData
from dagster._core.launcher import (
    CheckRunHealthResult,
    LaunchRunContext,
    ResumeRunContext,
    RunLauncher,
    WorkerStatus,
)
from dagster._grpc.types import ExecuteRunArgs, ResumeRunArgs
from dagster._serdes import ConfigurableClass, ConfigurableClassData, pack_value
from taskiq import AsyncBroker
from typing_extensions import Self, override

from dagster_taskiq.config import DEFAULT_CONFIG, TASK_EXECUTE_JOB_NAME, TASK_RESUME_JOB_NAME
from dagster_taskiq.defaults import task_default_queue, sqs_queue_url, aws_region_name
from dagster_taskiq.make_app import make_app
from dagster_taskiq.tags import (
    DAGSTER_TASKIQ_QUEUE_TAG,
    DAGSTER_TASKIQ_RUN_PRIORITY_TAG,
    DAGSTER_TASKIQ_TASK_ID_TAG,
)
from dagster_taskiq.tasks import create_execute_job_task, create_resume_job_task

if TYPE_CHECKING:
    from dagster._config import UserConfigSchema
    from taskiq.result import TaskiqResult


class TaskiqRunLauncher(RunLauncher, ConfigurableClass):
    """Dagster Run Launcher which starts runs as Taskiq tasks on AWS SQS.

    This launcher submits full Dagster runs as Taskiq tasks, which are distributed
    via AWS SQS to worker processes.
    """

    _instance: DagsterInstance  # pyright: ignore[reportIncompatibleMethodOverride]
    broker: AsyncBroker

    def __init__(
        self,
        default_queue: str,
        queue_url: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        config_source: Optional[dict] = None,
        inst_data: Optional[ConfigurableClassData] = None,
    ) -> None:
        """Initialize the Taskiq run launcher.

        Args:
            default_queue: Default queue name for runs
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
        self.config_source = dict(
            DEFAULT_CONFIG, **check.opt_dict_param(config_source, "config_source")
        )
        self.default_queue = check.str_param(default_queue, "default_queue")

        # Create the Taskiq broker
        self.broker = make_app(app_args=self.app_args())

        super().__init__()

    def app_args(self) -> dict:
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

    def terminate(self, run_id: str) -> bool:
        """Terminate a running task.

        Note: Taskiq doesn't support task termination.
        This method returns False to indicate termination is not supported.

        Args:
            run_id: ID of the run to terminate

        Returns:
            False (termination not supported)
        """
        run = self._instance.get_run_by_id(run_id)
        if run is None:
            return False

        # Taskiq doesn't support task termination
        # Workers will continue processing but we mark intent to stop
        self._instance.report_engine_event(
            "Taskiq does not support task termination. Task will complete normally.",
            run,
            cls=self.__class__,
        )

        return False

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
        task_args: dict,
        routing_key: str,
    ) -> None:
        """Launch a Taskiq task for the run.

        Args:
            run: The Dagster run
            task: The Taskiq task function
            task_args: Arguments to pass to the task
            routing_key: Task routing identifier
        """
        run_priority = _get_run_priority(run)
        queue = run.tags.get(DAGSTER_TASKIQ_QUEUE_TAG, self.default_queue)

        self._instance.report_engine_event(
            "Creating Taskiq run worker job task",
            run,
            cls=self.__class__,
        )

        # Submit task asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Use kiq() to submit the task with labels
            result = loop.run_until_complete(
                task.kiq(
                    **task_args,
                    labels={
                        "priority": str(run_priority),
                        "queue": queue,
                        "routing_key": routing_key,
                    },
                )
            )

            # Store the task ID for tracking
            task_id = result.task_id if hasattr(result, 'task_id') else str(id(result))

            self._instance.add_run_tags(
                run.run_id,
                {DAGSTER_TASKIQ_TASK_ID_TAG: task_id},
            )

            self._instance.report_engine_event(
                "Taskiq task has been forwarded to SQS.",
                run,
                EngineEventData(
                    {
                        "Run ID": run.run_id,
                        "Taskiq Task ID": task_id,
                        "Queue": queue,
                    }
                ),
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

    def check_run_worker_health(self, run: DagsterRun) -> CheckRunHealthResult:
        """Check the health status of a running task.

        Args:
            run: The Dagster run to check

        Returns:
            Health check result
        """
        if DAGSTER_TASKIQ_TASK_ID_TAG not in run.tags:
            return CheckRunHealthResult(WorkerStatus.UNKNOWN, "No task ID found for run")

        task_id = run.tags[DAGSTER_TASKIQ_TASK_ID_TAG]

        # Taskiq's result backend would need to be configured to check status
        # For now, we return UNKNOWN since we don't have a result backend configured
        # In a production setup, you'd configure a result backend and check it here
        return CheckRunHealthResult(
            WorkerStatus.UNKNOWN,
            f"Task {task_id} status cannot be determined without result backend"
        )

    @override
    def get_run_worker_debug_info(
        self, run: DagsterRun, include_container_logs: Optional[bool] = True
    ) -> Optional[str]:
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

        return str(
            {
                "run_id": run.run_id,
                "taskiq_task_id": task_id,
                "queue_url": self.queue_url,
                "region": self.region_name,
            }
        )

    @property
    def inst_data(self) -> Optional[ConfigurableClassData]:
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
                description=(
                    "The URL of the SQS queue. Default: environment variable "
                    "DAGSTER_TASKIQ_SQS_QUEUE_URL."
                ),
            ),
            "region_name": Field(
                Noneable(StringSource),
                is_required=False,
                description=(
                    "AWS region name. Default: environment variable AWS_DEFAULT_REGION "
                    "or us-east-1."
                ),
            ),
            "endpoint_url": Field(
                Noneable(StringSource),
                is_required=False,
                description="Custom AWS endpoint URL (for LocalStack). Default: None.",
            ),
            "default_queue": Field(
                StringSource,
                is_required=False,
                description=(
                    "The default queue to use when a run does not specify "
                    "Taskiq queue tag."
                ),
                default_value=task_default_queue,
            ),
            "config_source": Field(
                Noneable(Permissive()),
                is_required=False,
                description="Additional settings for the Taskiq broker.",
            ),
        }

    @classmethod
    def from_config_value(
        cls, inst_data: ConfigurableClassData, config_value: Mapping[str, Any]
    ) -> Self:
        """Create a launcher instance from configuration.

        Args:
            inst_data: Instance data
            config_value: Configuration values

        Returns:
            TaskiqRunLauncher instance
        """
        return cls(inst_data=inst_data, **config_value)


def _get_run_priority(run: DagsterRun) -> int:
    """Get the priority for a run from its tags.

    Args:
        run: The Dagster run

    Returns:
        Priority value (0 if not set or invalid)
    """
    if DAGSTER_TASKIQ_RUN_PRIORITY_TAG not in run.tags:
        return 0
    try:
        return int(run.tags[DAGSTER_TASKIQ_RUN_PRIORITY_TAG])
    except ValueError:
        return 0
