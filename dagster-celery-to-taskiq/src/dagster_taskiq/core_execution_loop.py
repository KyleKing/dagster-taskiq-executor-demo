import asyncio
import sys
from typing import Any, AsyncGenerator, Callable, cast

import dagster._check as check
from dagster._core.errors import DagsterSubprocessError
from dagster._core.events import DagsterEvent, EngineEventData
from dagster._core.execution.context.system import PlanOrchestrationContext
from dagster._core.execution.plan.instance_concurrency_context import InstanceConcurrencyContext
from dagster._core.execution.plan.plan import ExecutionPlan

from dagster._core.storage.tags import PRIORITY_TAG
from dagster._utils.error import serializable_error_info_from_exc_info
from dagster_shared.serdes import deserialize_value

from dagster_taskiq.defaults import task_default_priority, task_default_queue
from dagster_taskiq.executor import TaskiqExecutor
from dagster_taskiq.make_app import make_app
from dagster_taskiq.tags import (
    DAGSTER_TASKIQ_QUEUE_TAG,
    DAGSTER_TASKIQ_RUN_PRIORITY_TAG,
    DAGSTER_TASKIQ_STEP_PRIORITY_TAG,
)

TICK_SECONDS = 1
DELEGATE_MARKER = "taskiq_queue_wait"


async def core_taskiq_execution_loop(
    job_context: PlanOrchestrationContext,
    execution_plan: ExecutionPlan,
    step_execution_fn: Callable[..., Any],
) -> AsyncGenerator[DagsterEvent, None]:
    """Core execution loop for taskiq-based distributed execution.

    Args:
        job_context: The plan orchestration context
        execution_plan: The execution plan
        step_execution_fn: Function to submit a step for execution

    Yields:
        DagsterEvent objects
    """
    check.inst_param(job_context, "job_context", PlanOrchestrationContext)
    check.inst_param(execution_plan, "execution_plan", ExecutionPlan)
    check.callable_param(step_execution_fn, "step_execution_fn")

    # If there are no step keys to execute, then any io managers will not be used.
    if len(execution_plan.step_keys_to_execute) > 0:
        # https://github.com/dagster-io/dagster/issues/2440
        check.invariant(
            execution_plan.artifacts_persisted,
            "Cannot use in-memory storage with Taskiq, use filesystem (on top of NFS or "
            "similar system that allows files to be available to all nodes), S3, or GCS",
        )

    broker = make_app(cast(TaskiqExecutor, job_context.executor).app_args())

    priority_for_step = lambda step: (  # type: ignore
        -1 * int(step.tags.get(DAGSTER_TASKIQ_STEP_PRIORITY_TAG, task_default_priority))  # type: ignore
        + -1 * _get_run_priority(job_context)
    )
    priority_for_key = lambda step_key: (  # type: ignore
        priority_for_step(execution_plan.get_step_by_key(step_key))
    )
    _warn_on_priority_misuse(job_context, execution_plan)

    step_results = {}  # Dict[str, dict] {'result': TaskiqResult, 'task_id': str}
    step_errors = {}

    with InstanceConcurrencyContext(
        job_context.instance, job_context.dagster_run
    ) as instance_concurrency_context:
        with execution_plan.start(
            retry_mode=job_context.executor.retries,
            sort_key_fn=priority_for_step,
            instance_concurrency_context=instance_concurrency_context,
        ) as active_execution:
            stopping = False

            while (not active_execution.is_complete and not stopping) or step_results:
                if active_execution.check_for_interrupts():
                    yield DagsterEvent.engine_event(
                        job_context,
                        "Taskiq executor: received termination signal",
                        EngineEventData.interrupted(list(step_results.keys())),
                    )
                    stopping = True
                    active_execution.mark_interrupted()
                    # Cancel running tasks (not supported by current broker)
                    # TODO: Implement cancellation when CancellableSQSBroker is used
                    pass

                results_to_pop = []
                for step_key, data in sorted(
                    step_results.items(), key=lambda x: priority_for_key(x[0])  # type: ignore
                ):
                    result = data['result']
                    # Check if result is ready
                    is_ready = await result.is_ready()

                    if is_ready:
                        try:
                            task_result = await result.get_result()
                            # taskiq results are wrapped in TaskiqResult with return_value
                            if hasattr(task_result, 'return_value'):
                                step_events = task_result.return_value
                            else:
                                step_events = task_result
                        except Exception:
                            # Handle errors from task execution
                            step_events = []
                            step_errors[step_key] = serializable_error_info_from_exc_info(
                                sys.exc_info()
                            )

                        for step_event in step_events:
                            event = deserialize_value(step_event, DagsterEvent)
                            yield event
                            active_execution.handle_event(event)

                        results_to_pop.append(step_key)

                for step_key in results_to_pop:
                    if step_key in step_results:
                        del step_results[step_key]
                        active_execution.verify_complete(job_context, step_key)

                # process skips from failures or uncovered inputs
                for event in active_execution.plan_events_iterator(job_context):
                    yield event

                # don't add any new steps if we are stopping
                if stopping or step_errors:
                    continue

                # Submit new steps for execution
                for step in active_execution.get_steps_to_execute():  # type: ignore
                    try:
                        queue = step.tags.get(DAGSTER_TASKIQ_QUEUE_TAG, task_default_queue)
                        yield DagsterEvent.engine_event(
                            job_context.for_step(step),
                            f'Submitting taskiq task for step "{step.key}" to queue "{queue}".',
                            EngineEventData(marker_start=DELEGATE_MARKER),
                        )

                        # Get the priority for this step
                        priority = _get_step_priority(job_context, step)

                        # Submit the task
                        step_results[step.key] = await step_execution_fn(
                            broker,
                            job_context,
                            step,
                            queue,
                            priority,
                            active_execution.get_known_state(),
                        )

                    except Exception:
                        yield DagsterEvent.engine_event(
                            job_context,
                            "Encountered error during taskiq task submission.",
                            event_specific_data=EngineEventData.engine_error(
                                serializable_error_info_from_exc_info(sys.exc_info()),
                            ),
                        )
                        raise

                await asyncio.sleep(TICK_SECONDS)

            if step_errors:
                raise DagsterSubprocessError(
                    "During taskiq execution errors occurred in workers:\n{error_list}".format(
                        error_list="\n".join(
                            [f"[{key}]: {err.to_string()}" for key, err in step_errors.items()]
                        )
                    ),
                    subprocess_error_infos=list(step_errors.values()),
                )





def _get_step_priority(context: PlanOrchestrationContext, step: Any) -> int:
    """Step priority is (currently) set as the overall run priority plus the individual
    step priority.
    """
    run_priority = _get_run_priority(context)
    step_priority = int(step.tags.get(DAGSTER_TASKIQ_STEP_PRIORITY_TAG, task_default_priority))
    priority = run_priority + step_priority
    return priority


def _get_run_priority(context: PlanOrchestrationContext) -> int:
    tag_value = context.get_tag(DAGSTER_TASKIQ_RUN_PRIORITY_TAG)
    if tag_value is None:
        return 0
    try:
        return int(tag_value)
    except ValueError:
        return 0


def _warn_on_priority_misuse(context: PlanOrchestrationContext, execution_plan: ExecutionPlan) -> None:
    bad_keys = []
    for key in execution_plan.step_keys_to_execute:
        step = execution_plan.get_step_by_key(key)
        if (
            step.tags.get(PRIORITY_TAG) is not None  # type: ignore
            and step.tags.get(DAGSTER_TASKIQ_STEP_PRIORITY_TAG) is None  # type: ignore
        ):
            bad_keys.append(key)

    if bad_keys:
        context.log.warning(
            'The following steps do not have "dagster-taskiq/priority" set but do '
            'have "dagster/priority" set which is not applicable for the taskiq engine: [{}]. '
            "Consider using a function to set both keys.".format(", ".join(bad_keys))
        )
