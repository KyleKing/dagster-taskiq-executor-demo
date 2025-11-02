# Modifications copyright (c) 2024 dagster-taskiq contributors

"""TaskIQ executor implementation for Dagster."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

from dagster import (
    DagsterEvent,
    ExecutorRequirement,
    InitExecutorContext,
    executor,
)
from dagster._core.execution.plan.objects import StepFailureData, StepSuccessData
from dagster._core.execution.plan.step import StepKind
from dagster._core.executor.base import Executor
from dagster._core.execution.retries import RetryMode
from dagster_shared.error import SerializableErrorInfo

from .broker import SqsBroker
from .models import IdempotencyStorage, get_idempotency_storage
from .task_payloads import ExecutionResult, IdempotencyRecord, OpExecutionTask, TaskState
from .worker import TaskIQWorker

__all__ = [
    "ExecutionResult",
    "IdempotencyRecord",
    "IdempotencyStorage",
    "OpExecutionTask",
    "SqsBroker",
    "TaskIQExecutor",
    "TaskIQWorker",
    "TaskState",
    "get_idempotency_storage",
    "taskiq_executor",
]


class TaskIQExecutor(Executor):
    """Dagster executor that dispatches ops to TaskIQ workers via SQS."""

    def __init__(self, broker: SqsBroker, retries: RetryMode | None = None) -> None:
        """Initialize the TaskIQ executor."""
        self.broker = broker
        self._retries = retries or RetryMode(RetryMode.DISABLED)
        self.logger = logging.getLogger(__name__)
        self.pending_steps: dict[str, str] = {}  # step_key -> idempotency_key
        self._idempotency_storage = get_idempotency_storage()

    @property
    def retries(self):
        """Return retry mode for this executor."""
        return self._retries



    def execute(self, plan_context: Any, execution_plan: Any) -> Iterator[DagsterEvent]:
        """Execute the plan by dispatching steps to TaskIQ workers."""
        self.logger.info("Starting TaskIQ execution for run %s", plan_context.run_id)

        try:
            # Start the broker synchronously
            self.broker.startup_sync()

            # Submit all steps to TaskIQ
            for step in execution_plan.steps:
                if step.kind == StepKind.COMPUTE:
                    yield from self._submit_step(plan_context, step)

            # Poll for results and yield events
            yield from self._poll_for_results(plan_context, execution_plan)

        except Exception as e:
            self.logger.exception("Error during TaskIQ execution: %s", e)
            raise
        finally:
            # Shutdown the broker
            try:
                self.broker.shutdown_sync()
            except Exception as e:
                self.logger.exception("Error shutting down broker: %s", e)

    def _submit_step(self, plan_context: Any, step: Any) -> Iterator[DagsterEvent]:
        """Submit a single step to TaskIQ for execution."""
        step_key = step.key
        idempotency_key = f"{plan_context.run_id}:{step_key}"

        self.logger.info("Submitting step %s to TaskIQ", step_key)

        # Check idempotency
        if self._idempotency_storage.is_completed(idempotency_key):
            self.logger.info("Step %s already completed, skipping", step_key)
            # Yield completion events for already completed step
            yield from self._yield_completion_events(plan_context, step, TaskState.COMPLETED)
            return

        # Create task payload
        task = OpExecutionTask(
            run_id=plan_context.run_id,
            step_keys_to_execute=[step_key],
            instance_ref_dict=plan_context.instance.get_ref().to_dict(),
            reconstructable_job_dict=plan_context.reconstructable_job.to_dict(),
            retry_mode_dict=self.retries.to_dict(),
            known_state_dict=None,  # TODO: implement known state
        )

        # Create idempotency record
        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            state=TaskState.PENDING,
            task_data=task.to_json(),
        )
        self._idempotency_storage.save_record(record)

        # Track pending step
        self.pending_steps[step_key] = idempotency_key

        # Submit task to broker
        try:
            self.broker.send_message_sync(task.to_json())
            self.logger.info("Step %s submitted to TaskIQ successfully", step_key)

            # Mark as running
            self._idempotency_storage.update_state(idempotency_key, TaskState.RUNNING)

            # Yield step start event
            step_context = plan_context.for_step(step)
            yield DagsterEvent.step_start_event(step_context)

        except Exception as e:
            self.logger.exception("Failed to submit step %s to TaskIQ: %s", step_key, e)
            self._idempotency_storage.update_state(idempotency_key, TaskState.FAILED, str(e))
            step_context = plan_context.for_step(step)
            yield DagsterEvent.step_failure_event(
                step_context=step_context,
                step_failure_data=StepFailureData(
                    error=SerializableErrorInfo(str(e), [], "Exception"), user_failure_data=None
                ),
            )

    def _poll_for_results(self, plan_context: Any, execution_plan: Any) -> Iterator[DagsterEvent]:
        """Poll for task completion results and yield appropriate events."""
        self.logger.info("Polling for results of %d pending steps", len(self.pending_steps))

        timeout = 300.0  # 5 minutes default
        start_time = time.time()
        poll_interval = 2.0  # seconds

        while self.pending_steps and (time.time() - start_time) < timeout:
            completed_steps = []

            for step_key, idempotency_key in list(self.pending_steps.items()):
                record = self._idempotency_storage.get_record(idempotency_key)
                if not record:
                    continue

                # Check if task is completed
                if record.state in {TaskState.COMPLETED, TaskState.FAILED}:
                    completed_steps.append(step_key)
                    step = next((s for s in execution_plan.steps if s.key == step_key), None)
                    if step:
                        yield from self._yield_completion_events(plan_context, step, record.state)

            # Remove completed steps
            for step_key in completed_steps:
                self.pending_steps.pop(step_key, None)

            if self.pending_steps:
                time.sleep(poll_interval)

        # Handle timeout
        if self.pending_steps:
            self.logger.warning("Timeout waiting for %d steps to complete", len(self.pending_steps))
            for step_key in list(self.pending_steps.keys()):
                step = next((s for s in execution_plan.steps if s.key == step_key), None)
                if step:
                    step_context = plan_context.for_step(step)
                    yield DagsterEvent.step_failure_event(
                        step_context=step_context,
                        step_failure_data=StepFailureData(
                            error=SerializableErrorInfo("Task execution timeout", [], "Exception"),
                            user_failure_data=None,
                        ),
                    )

    def _yield_completion_events(self, plan_context: Any, step: Any, state: TaskState) -> Iterator[DagsterEvent]:
        """Yield completion events for a step."""
        step_context = plan_context.for_step(step)

        if state == TaskState.COMPLETED:
            yield DagsterEvent.step_success_event(step_context, StepSuccessData(duration_ms=0.0))
        elif state == TaskState.FAILED:
            idempotency_key = f"{plan_context.run_id}:{step.key}"
            record = self._idempotency_storage.get_record(idempotency_key)
            error_msg = record.result_data if record and record.result_data else "Unknown error"

            yield DagsterEvent.step_failure_event(
                step_context=step_context,
                step_failure_data=StepFailureData(
                    error=SerializableErrorInfo(error_msg, [], "Exception"), user_failure_data=None
                ),
            )

    def _resolve_inputs(self, step: Any, plan_context: Any) -> dict[str, Any]:
        """Resolve input values for a step."""
        # In a real implementation, this would resolve inputs from previous steps
        # For now, return empty dict as ops handle their own inputs
        return {}


@executor(
    name="taskiq",
    config_schema={
        "queue_url": str,
        "aws_endpoint_url": {"type": str, "default": None},
        "aws_region": {"type": str, "default": "us-east-1"},
        "aws_access_key_id": {"type": str, "default": None},
        "aws_secret_access_key": {"type": str, "default": None},
    },
    requirements=[
        ExecutorRequirement.RECONSTRUCTABLE_JOB,
        ExecutorRequirement.NON_EPHEMERAL_INSTANCE,
        ExecutorRequirement.PERSISTENT_OUTPUTS,
    ],
)
def taskiq_executor(init_context: InitExecutorContext) -> TaskIQExecutor:
    """Create a TaskIQ executor instance."""
    config = init_context.executor_config
    broker = SqsBroker(
        queue_url=config["queue_url"],
        aws_endpoint_url=config.get("aws_endpoint_url"),
        aws_region=config.get("aws_region", "us-east-1"),
        aws_access_key_id=config.get("aws_access_key_id"),
        aws_secret_access_key=config.get("aws_secret_access_key"),
    )
    return TaskIQExecutor(broker=broker, retries=RetryMode(RetryMode.DISABLED))