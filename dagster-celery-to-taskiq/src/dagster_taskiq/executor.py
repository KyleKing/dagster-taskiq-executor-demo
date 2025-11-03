import asyncio
from typing import Optional

from dagster import (
    Executor,
    Field,
    Noneable,
    Permissive,
    StringSource,
    _check as check,
    executor,
    multiple_process_executor_requirements,
)
from dagster._core.execution.retries import RetryMode, get_retries_config
from dagster._grpc.types import ExecuteStepArgs
from dagster._serdes import pack_value

from dagster_taskiq.config import DEFAULT_CONFIG, dict_wrapper
from dagster_taskiq.defaults import sqs_queue_url, aws_region_name

TASKIQ_CONFIG = {
    "queue_url": Field(
        Noneable(StringSource),
        is_required=False,
        description=(
            "The URL of the SQS queue. Default: "
            "environment variable DAGSTER_TASKIQ_SQS_QUEUE_URL."
        ),
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
def taskiq_executor(init_context):
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
    """
    return TaskiqExecutor(
        queue_url=init_context.executor_config.get("queue_url"),
        region_name=init_context.executor_config.get("region_name"),
        endpoint_url=init_context.executor_config.get("endpoint_url"),
        config_source=init_context.executor_config.get("config_source"),
        retries=RetryMode.from_config(init_context.executor_config["retries"]),
    )


async def _submit_task_async(broker, plan_context, step, queue, priority, known_state):
    """Submit a task asynchronously using taskiq.

    This function is async because taskiq's kiq() method is async.
    """
    from dagster_taskiq.tasks import create_task

    # Ensure broker is started
    await broker.startup()

    # Ensure result backend is started if it exists
    if hasattr(broker, 'result_backend') and broker.result_backend:
        await broker.result_backend.startup()

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

    # Calculate delay based on priority (higher priority = lower delay)
    # Priority is typically 0-10, map to delay_seconds (0-900 max for SQS)
    delay_seconds = max(0, min(900, priority * 10))  # 10 seconds per priority level

    # Use kicker with delay label for taskiq-aio-sqs
    task_result = await task.kicker().with_labels(delay=delay_seconds).kiq(
        execute_step_args_packed=pack_value(execute_step_args),
        executable_dict=plan_context.reconstructable_job.to_dict(),
    )

    return {'result': task_result, 'task_id': str(task_result.task_id)}





class TaskiqExecutor(Executor):
    def __init__(
        self,
        retries,
        queue_url: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        config_source: Optional[dict] = None,
    ):
        self.queue_url = check.opt_str_param(queue_url, "queue_url", default=sqs_queue_url)
        self.region_name = check.opt_str_param(region_name, "region_name", default=aws_region_name)
        self.endpoint_url = check.opt_str_param(endpoint_url, "endpoint_url")
        self.config_source = dict_wrapper(
            dict(DEFAULT_CONFIG, **check.opt_dict_param(config_source, "config_source"))
        )
        self._retries = check.inst_param(retries, "retries", RetryMode)

    @property
    def retries(self):
        return self._retries

    def execute(self, plan_context, execution_plan):
        from dagster_taskiq.core_execution_loop import core_taskiq_execution_loop

        # Run the async generator in a new event loop and yield synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async_gen = core_taskiq_execution_loop(
                plan_context, execution_plan, step_execution_fn=_submit_task_async
            )
            while True:
                try:
                    event = loop.run_until_complete(async_gen.__anext__())
                    yield event
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    @staticmethod
    def for_cli(
        queue_url: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        config_source: Optional[dict] = None,
    ):
        return TaskiqExecutor(
            retries=RetryMode(RetryMode.DISABLED),
            queue_url=queue_url,
            region_name=region_name,
            endpoint_url=endpoint_url,
            config_source=config_source,
        )

    def app_args(self):
        return {
            "queue_url": self.queue_url,
            "region_name": self.region_name,
            "endpoint_url": self.endpoint_url,
            "config_source": self.config_source,
            "retries": self.retries,
        }
