"""Core execution loop for Taskiq-based distributed execution.

This module provides the main execution loop that coordinates task submission,
result retrieval, and event handling for Dagster runs executed via Taskiq.
"""

import asyncio
import sys
import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Any, cast

import dagster._check as check  # noqa: PLC2701
from dagster._core.errors import DagsterSubprocessError  # noqa: PLC2701
from dagster._core.events import DagsterEvent, EngineEventData  # noqa: PLC2701
from dagster._core.execution.context.system import PlanOrchestrationContext  # noqa: PLC2701
from dagster._core.execution.plan.instance_concurrency_context import InstanceConcurrencyContext  # noqa: PLC2701
from dagster._core.execution.plan.plan import ExecutionPlan  # noqa: PLC2701
from dagster._utils.error import serializable_error_info_from_exc_info  # noqa: PLC2701
from dagster_shared.serdes import deserialize_value

from dagster_taskiq.make_app import make_app

TICK_SECONDS = 1
DELEGATE_MARKER = "taskiq_queue_wait"


# FIXME: refactor into smaller composable private functions
async def core_taskiq_execution_loop(  # noqa: C901, PLR0912, PLR0915
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

    # FIXME: Lazy import to avoid circular dependency
    from dagster_taskiq.executor import TaskiqExecutor  # noqa: PLC0415

    broker = make_app(cast("TaskiqExecutor", job_context.executor).app_args())

    step_results: dict[str, dict[str, Any]] = {}  # {'result': AsyncTaskiqTask, 'task_id': str, 'waiter': asyncio.Task}
    step_errors = {}
    cancelled_task_ids: set[str] = set()

    async def _check_task_cancelled(task_id: str) -> bool:
        """Check if a task has been cancelled.

        Args:
            task_id: The task ID to check

        Returns:
            True if the task has been cancelled, False otherwise
        """
        # Check if cancellation was requested locally
        if task_id in cancelled_task_ids:
            return True

        # Check if cancellation was requested externally (via launcher terminate())
        # by checking the Dagster run status. If the run is being cancelled,
        # all tasks for that run should be considered cancelled.
        try:
            run = job_context.instance.get_run_by_id(job_context.dagster_run.run_id)
            if run and run.status.value in ("CANCELING", "CANCELED"):  # type: ignore[union-attr]
                return True
        except Exception:
            # If we can't check run status, continue waiting
            job_context.log.debug("Could not check run status for cancellation: %s", task_id)

        return False

    async def _request_task_cancellations(reason: str) -> None:
        """Ask the broker to cancel any in-flight TaskIQ tasks."""
        cancel_callable = getattr(broker, "cancel_task", None)
        if not callable(cancel_callable):
            return

        pending = []
        for data in step_results.values():
            task_id = data.get("task_id")
            if not task_id or task_id in cancelled_task_ids:
                continue
            try:
                task_uuid = uuid.UUID(str(task_id))
            except (TypeError, ValueError):
                continue
            cancelled_task_ids.add(task_id)
            pending.append(cancel_callable(task_uuid))

        if not pending:
            return

        job_context.log.debug("Requesting cancellation for %d taskiq tasks (%s).", len(pending), reason)
        results = await asyncio.gather(*pending, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                job_context.log.warning("Taskiq task cancellation failed: %s", result)

    async def _cancel_waiters() -> None:
        """Ensure waiter tasks are cancelled/awaited before exiting."""
        waiters = [
            data.get("waiter") for data in list(step_results.values()) if isinstance(data.get("waiter"), asyncio.Task)
        ]
        if not waiters:
            return

        for waiter in waiters:
            if waiter is not None and not waiter.done():
                waiter.cancel()

        filtered_waiters = [w for w in waiters if w is not None]
        await asyncio.gather(*filtered_waiters, return_exceptions=True)

    with InstanceConcurrencyContext(job_context.instance, job_context.dagster_run) as instance_concurrency_context:  # noqa: PLR1702, SIM117
        with execution_plan.start(
            retry_mode=job_context.executor.retries,
            sort_key_fn=None,
            instance_concurrency_context=instance_concurrency_context,
        ) as active_execution:
            stopping = False

            try:
                while (not active_execution.is_complete and not stopping) or step_results:
                    if active_execution.check_for_interrupts():
                        yield DagsterEvent.engine_event(
                            job_context,
                            "Taskiq executor: received termination signal",
                            EngineEventData.interrupted(list(step_results.keys())),
                        )
                        stopping = True
                        active_execution.mark_interrupted()
                        await _request_task_cancellations(reason="termination signal")

                    results_to_pop = []
                    for step_key, data in step_results.items():
                        waiter = data["waiter"]
                        if not waiter.done():
                            continue

                        try:
                            task_result = waiter.result()

                            if task_result is not None:
                                # Handle TaskiqResult objects that may wrap the actual return value
                                if hasattr(task_result, "raise_for_error"):
                                    task_result.raise_for_error()
                                if hasattr(task_result, "return_value"):
                                    step_events = task_result.return_value
                                else:
                                    step_events = task_result
                            else:
                                step_events = None
                        except asyncio.CancelledError:
                            # Task was cancelled - handle gracefully
                            job_context.log.info(
                                "Step %s was cancelled while waiting for result",
                                step_key,
                            )
                            yield DagsterEvent.engine_event(
                                job_context,
                                f'Step "{step_key}" was cancelled',
                                EngineEventData.interrupted([step_key]),
                            )
                            step_events = []
                            # Mark as cancelled in the set
                            task_id = data.get("task_id")
                            if task_id:
                                cancelled_task_ids.add(task_id)
                        except Exception:
                            job_context.log.exception(
                                "Error getting result for step %s",
                                step_key,
                            )
                            step_events = []
                            step_errors[step_key] = serializable_error_info_from_exc_info(sys.exc_info())
                            await _request_task_cancellations(reason="step failure")

                        # Handle None or non-iterable step_events
                        if step_events is None:
                            job_context.log.warning("Step %s returned None result. Events may be missing.", step_key)
                            step_events = []
                        elif not isinstance(step_events, (list, tuple)):
                            job_context.log.warning(
                                "Step %s returned non-list result: %s. Attempting to convert to list.",
                                step_key,
                                type(step_events),
                            )
                            # If it's not a list/tuple, try to make it iterable
                            step_events = [step_events] if step_events else []

                        for step_event in step_events:
                            event = deserialize_value(step_event, DagsterEvent)
                            yield event
                            active_execution.handle_event(event)

                        results_to_pop.append(step_key)

                    for step_key in results_to_pop:
                        if step_key in step_results:
                            del step_results[step_key]
                            active_execution.verify_complete(job_context, step_key)

                    for event in active_execution.plan_events_iterator(job_context):
                        yield event

                    if stopping or step_errors:
                        await asyncio.sleep(TICK_SECONDS)
                        continue

                    for step in active_execution.get_steps_to_execute():
                        try:
                            yield DagsterEvent.engine_event(
                                job_context.for_step(step),
                                f'Submitting taskiq task for step "{step.key}".',
                                EngineEventData(marker_start=DELEGATE_MARKER),
                            )

                            step_results[step.key] = await step_execution_fn(
                                broker,
                                job_context,
                                step,
                                active_execution.get_known_state(),
                            )
                            result_handle = step_results[step.key]["result"]
                            task_id = step_results[step.key]["task_id"]
                            step_key_for_wait = step.key

                            # Create a waiter that tries wait_result() first, then falls back to
                            # direct S3 backend access
                            async def _wait_for_result() -> Any:
                                """Wait for task result, using S3 backend if wait_result() fails.

                                Periodically checks for cancellation while waiting.

                                Returns:
                                    The task result value

                                Raises:
                                    asyncio.CancelledError: If the task has been cancelled
                                """
                                # Capture loop variables to avoid B023
                                captured_result_handle = result_handle  # noqa: B023
                                captured_task_id = task_id  # noqa: B023
                                captured_step_key = step_key_for_wait  # noqa: B023

                                try:
                                    # First try the standard wait_result() method
                                    wait_result_fn = getattr(captured_result_handle, "wait_result", None)
                                    if wait_result_fn:
                                        # Check for cancellation before waiting
                                        if await _check_task_cancelled(captured_task_id):
                                            raise asyncio.CancelledError(
                                                f"Task {captured_task_id} for step {captured_step_key} was cancelled"
                                            )

                                        result = await wait_result_fn()
                                        if result is not None:
                                            return result

                                    # If wait_result() returned None or doesn't exist, use S3 backend directly
                                    if hasattr(broker, "result_backend") and broker.result_backend and captured_task_id:  # type: ignore[truthy-bool]
                                        job_context.log.debug(
                                            "Using S3 result backend directly for step %s, task %s",
                                            captured_step_key,
                                            captured_task_id,
                                        )
                                        # Poll the S3 backend until result is ready
                                        result_backend = broker.result_backend
                                        max_wait_seconds = 300  # 5 minutes max wait
                                        wait_interval = 0.5  # Check every 500ms
                                        elapsed = 0

                                        while elapsed < max_wait_seconds:
                                            # Check for cancellation periodically
                                            if await _check_task_cancelled(captured_task_id):
                                                job_context.log.info(
                                                    "Task %s for step %s was cancelled while waiting for result",
                                                    captured_task_id,
                                                    captured_step_key,
                                                )
                                                raise asyncio.CancelledError(
                                                    f"Task {captured_task_id} for step {captured_step_key} was cancelled"
                                                )

                                            try:
                                                if await result_backend.is_result_ready(captured_task_id):
                                                    backend_result = await result_backend.get_result(captured_task_id)
                                                    if hasattr(backend_result, "return_value"):
                                                        return backend_result.return_value
                                                    return backend_result
                                            except Exception as e:
                                                # Result not ready yet, continue waiting
                                                if "ResultIsMissingError" not in str(type(e)):
                                                    job_context.log.debug(
                                                        "Error checking result for step %s: %s",
                                                        captured_step_key,
                                                        e,
                                                    )

                                            await asyncio.sleep(wait_interval)
                                            elapsed = int(elapsed + wait_interval)

                                        msg = (
                                            f"Result for step {captured_step_key} (task {captured_task_id}) "
                                            f"not available after {max_wait_seconds}s"
                                        )
                                        raise TimeoutError(msg)  # noqa: TRY301

                                    # No result backend available
                                    return None  # noqa: TRY300

                                except asyncio.CancelledError:
                                    # Re-raise cancellation errors
                                    raise
                                except Exception:
                                    job_context.log.exception(
                                        "Error waiting for result for step %s",
                                        captured_step_key,
                                    )
                                    raise

                            step_results[step.key]["waiter"] = asyncio.create_task(_wait_for_result())

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
                    error_list = "\n".join([f"[{key}]: {err.to_string()}" for key, err in step_errors.items()])
                    msg = f"During taskiq execution errors occurred in workers:\n{error_list}"
                    raise DagsterSubprocessError(
                        msg,
                        subprocess_error_infos=list(step_errors.values()),
                    )
            finally:
                # Best-effort cancellation of any remaining remote tasks and waiter tasks.
                await _request_task_cancellations(reason="loop shutdown")
                await _cancel_waiters()
