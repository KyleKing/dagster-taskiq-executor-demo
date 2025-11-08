"""Taskiq executor for Dagster.

This module provides the TaskiqExecutor which uses AWS SQS for distributed task execution.
"""

import asyncio
from typing import TYPE_CHECKING, Any

from dagster import (
    Executor,
    Field,
    Noneable,
    Permissive,
    StringSource,
    executor,
    multiple_process_executor_requirements,
)
from dagster import (
    _check as check,  # noqa: PLC2701
)
from dagster._core.execution.retries import RetryMode, get_retries_config  # noqa: PLC2701
from dagster._grpc.types import ExecuteStepArgs  # noqa: PLC2701
from dagster._serdes import pack_value  # noqa: PLC2701

from dagster_taskiq.config import DEFAULT_CONFIG, DictWrapper
from dagster_taskiq.defaults import (
    aws_region_name,
    sqs_endpoint_url,
    sqs_queue_url,
)
from dagster_taskiq.tasks import create_task

if TYPE_CHECKING:
    from dagster._core.execution.context.system import PlanOrchestrationContext
    from dagster._core.execution.plan.plan import ExecutionPlan
    from taskiq import AsyncBroker

TASKIQ_CONFIG = {
    "queue_url": Field(
        Noneable(StringSource),
        is_required=False,
        description=("The URL of the SQS queue. Default: environment variable DAGSTER_TASKIQ_SQS_QUEUE_URL."),
    ),
    "region_name": Field(
        Noneable(StringSource),
        is_required=False,
        default_value=None,
        description="AWS region name. Default: environment variable AWS_DEFAULT_REGION or us-east-1.",
    ),
    "endpoint_url": Field(
        Noneable(StringSource),
        is_required=False,
        default_value=None,
        description="Custom AWS endpoint URL (for LocalStack). Default: None.",
    ),
    "config_source": Field(
        Noneable(Permissive()),
        is_required=False,
        description="Additional settings for the Taskiq broker.",
    ),
    "retries": get_retries_config(),
}


@executor(
    name="taskiq",
    config_schema=TASKIQ_CONFIG,
    requirements=multiple_process_executor_requirements(),
)
def taskiq_executor(init_context: Any) -> "TaskiqExecutor":
    """Taskiq-based executor.

    The Taskiq executor uses AWS SQS for task distribution and supports distributed
    execution of Dagster jobs.

    The executor exposes config settings for the underlying Taskiq broker under
    the ``config_source`` key.

    To use the `taskiq_executor`, set it as the `executor_def` when defining a job:

    .. code-block:: python

        from dagster import job
        from dagster_taskiq import taskiq_executor

        @job(executor_def=taskiq_executor)
        def taskiq_enabled_job():
            pass

    Then you can configure the executor as follows:

    .. code-block:: YAML

        execution:
          config:
            queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
            region_name: 'us-east-1'  # Optional
            endpoint_url: 'http://localhost:4566'  # Optional, for LocalStack
            config_source: # Dict[str, Any]: Any additional parameters to pass to the
                #...       # Taskiq broker.

    Note that the YAML you provide here must align with the configuration with which the Taskiq
    workers on which you hope to run were started. If, for example, you point the executor at a
    different queue than the one your workers are listening to, the workers will never be able to
    pick up tasks for execution.

    Args:
        init_context: The executor initialization context

    Returns:
        A configured TaskiqExecutor instance
    """
    return TaskiqExecutor(
        queue_url=init_context.executor_config.get("queue_url"),
        region_name=init_context.executor_config.get("region_name"),
        endpoint_url=init_context.executor_config.get("endpoint_url"),
        config_source=init_context.executor_config.get("config_source"),
        retries=RetryMode.from_config(init_context.executor_config.get("retries", {})),  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
    )


async def _submit_task_async(  # noqa: PLR0917
    broker: "AsyncBroker",
    plan_context: "PlanOrchestrationContext",
    step: Any,
    known_state: Any,
) -> dict[str, Any]:
    """Submit a task asynchronously using taskiq.

    This function is async because taskiq's kiq() method is async.

    Args:
        broker: The Taskiq broker instance
        plan_context: The plan orchestration context
        step: The step to execute
        known_state: The known execution state

    Returns:
        Dictionary containing 'result' and 'task_id' keys
    """
    # Ensure broker is started
    await broker.startup()

    # Ensure result backend is started if it exists
    if hasattr(broker, "result_backend") and broker.result_backend:  # type: ignore[truthy-bool]
        await broker.result_backend.startup()
        plan_context.log.debug(
            "Result backend configured: %s for step '%s'",
            type(broker.result_backend).__name__,
            step.key,
        )
    else:
        plan_context.log.warning(
            "No result backend configured on broker for step '%s'. Results may not be retrievable.",
            step.key,
        )

    execute_step_args = ExecuteStepArgs(
        job_origin=plan_context.reconstructable_job.get_python_origin(),
        run_id=plan_context.dagster_run.run_id,
        step_keys_to_execute=[step.key],
        instance_ref=plan_context.instance.get_ref(),
        retry_mode=plan_context.executor.retries.for_inner_plan(),
        known_state=known_state,
        print_serialized_events=True,
    )

    task = create_task(broker)

    # Submit task to queue
    task_result = await task.kiq(
        execute_step_args_packed=pack_value(execute_step_args),
        executable_dict=plan_context.reconstructable_job.to_dict(),
    )

    # Verify task result has access to result backend
    if hasattr(task_result, "broker") and hasattr(task_result.broker, "result_backend"):
        backend_name = type(task_result.broker.result_backend).__name__ if task_result.broker.result_backend else "None"
        plan_context.log.debug(
            "Task result for step '%s' has result backend: %s",
            step.key,
            backend_name,
        )

    return {"result": task_result, "task_id": str(task_result.task_id)}


class TaskiqExecutor(Executor):
    """Executor that uses Taskiq for distributed task execution via AWS SQS."""

    def __init__(
        self,
        retries: RetryMode,
        queue_url: str | None = None,
        region_name: str | None = None,
        endpoint_url: str | None = None,
        config_source: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the Taskiq executor.

        Args:
            retries: The retry mode configuration
            queue_url: SQS queue URL
            region_name: AWS region name
            endpoint_url: Custom AWS endpoint URL (for LocalStack)
            config_source: Additional configuration for the Taskiq broker
        """
        self.queue_url = check.opt_str_param(queue_url, "queue_url", default=sqs_queue_url)
        self.region_name = check.opt_str_param(region_name, "region_name", default=aws_region_name)
        self.endpoint_url = check.opt_str_param(
            endpoint_url,
            "endpoint_url",
            default=sqs_endpoint_url,
        )
        self.config_source = DictWrapper(dict(DEFAULT_CONFIG, **check.opt_dict_param(config_source, "config_source")))
        self._retries = check.inst_param(retries, "retries", RetryMode)

    @property
    def retries(self) -> RetryMode:
        """Get the retry mode configuration.

        Returns:
            The retry mode
        """
        return self._retries

    def execute(self, plan_context: "PlanOrchestrationContext", execution_plan: "ExecutionPlan") -> Any:  # noqa: PLR6301
        """Execute the plan using Taskiq.

        Args:
            plan_context: The plan orchestration context
            execution_plan: The execution plan

        Yields:
            Dagster events from execution
        """
        from dagster_taskiq.core_execution_loop import core_taskiq_execution_loop  # noqa: PLC0415

        # Run the async generator in a new event loop and yield synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async_gen = core_taskiq_execution_loop(plan_context, execution_plan, step_execution_fn=_submit_task_async)
            while True:
                try:
                    event = loop.run_until_complete(anext(async_gen))
                    yield event
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    @staticmethod
    def for_cli(
        queue_url: str | None = None,
        region_name: str | None = None,
        endpoint_url: str | None = None,
        config_source: dict[str, Any] | None = None,
    ) -> "TaskiqExecutor":
        """Create an executor instance for CLI use.

        Args:
            queue_url: SQS queue URL
            region_name: AWS region name
            endpoint_url: Custom AWS endpoint URL
            config_source: Additional configuration

        Returns:
            A TaskiqExecutor instance configured for CLI use
        """
        return TaskiqExecutor(
            retries=RetryMode(RetryMode.DISABLED),
            queue_url=queue_url,
            region_name=region_name,
            endpoint_url=endpoint_url,
            config_source=config_source,
        )

    def app_args(self) -> dict[str, Any]:
        """Get application arguments for broker creation.

        Returns:
            Dictionary of broker configuration arguments
        """
        return {
            "queue_url": self.queue_url,
            "region_name": self.region_name,
            "endpoint_url": self.endpoint_url,
            "config_source": self.config_source,
            "retries": self.retries,
        }
