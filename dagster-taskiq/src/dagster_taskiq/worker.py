# Modifications copyright (c) 2024 dagster-taskiq contributors

"""TaskIQ worker for executing Dagster ops from SQS messages."""

import asyncio
import json
import logging
from datetime import UTC, datetime

import aioboto3

from .models import get_idempotency_storage
from .task_payloads import ExecutionResult, OpExecutionTask, TaskState


class TaskIQWorker:
    """Async worker for processing Dagster op execution tasks from SQS."""

    def __init__(
        self,
        queue_url: str,
        aws_endpoint_url: str | None = None,
        aws_region: str = "us-east-1",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        visibility_timeout: int = 300,
    ) -> None:
        """Initialize the TaskIQ worker."""
        self.queue_url = queue_url
        self.aws_endpoint_url = aws_endpoint_url
        self.aws_region = aws_region
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.visibility_timeout = visibility_timeout
        self.logger = logging.getLogger(__name__)
        self.idempotency_storage = get_idempotency_storage()
        self.running = False

        # Create SQS client
        self.sqs_client = aioboto3.client(
            "sqs",
            endpoint_url=aws_endpoint_url,
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

    async def startup(self) -> None:
        """Start the worker."""
        self.logger.info("Starting TaskIQ worker for queue: %s", self.queue_url)
        self.running = True

    async def shutdown(self) -> None:
        """Shutdown the worker."""
        self.logger.info("Shutting down TaskIQ worker")
        self.running = False
        await self.sqs_client.close()

    async def run(self) -> None:
        """Run the worker loop."""
        try:
            await self.startup()
            await self._run_worker_loop()
        except KeyboardInterrupt:
            self.logger.info("Worker interrupted")
        finally:
            await self.shutdown()

    async def _run_worker_loop(self) -> None:
        """Run the main worker loop to consume SQS messages."""
        self.logger.info("Starting worker loop")

        while self.running:
            try:
                # Receive messages from SQS
                response = await self.sqs_client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,  # Long polling
                    VisibilityTimeout=self.visibility_timeout,
                )

                messages = response.get("Messages", [])
                if not messages:
                    continue

                message = messages[0]
                receipt_handle = message["ReceiptHandle"]
                body = message["Body"]

                # Process the message
                await self._execute_op_task(body)

                # Delete the message after successful processing
                await self.sqs_client.delete_message(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=receipt_handle,
                )
                self.logger.debug("Message processed and deleted")

            except Exception as e:
                self.logger.exception("Error in worker loop: %s", e)
                await asyncio.sleep(5)  # Back off on errors

    async def _execute_op_task(self, task_data: str) -> None:
        """Execute a single op task."""
        try:
            # Parse task
            task = OpExecutionTask.from_json(task_data)
            step_keys_str = ", ".join(task.step_keys_to_execute)
            self.logger.info("Processing task for steps %s in run %s", step_keys_str, task.run_id)

            # Use run_id as idempotency key for now
            idempotency_key = task.run_id

            # Check idempotency - if already completed, skip
            if self.idempotency_storage.is_completed(idempotency_key):
                self.logger.info("Task %s already completed, skipping", idempotency_key)
                return

            # Mark as running
            self.idempotency_storage.update_state(idempotency_key, TaskState.RUNNING)

            # Execute the step
            await self._execute_step(task)

            # Update idempotency with result
            self.idempotency_storage.update_state(idempotency_key, TaskState.COMPLETED)

            self.logger.info("Task %s completed", idempotency_key)

        except Exception as e:
            self.logger.exception("Error executing op task: %s", e)
            # Try to extract run_id from task data for error reporting
            try:
                task = OpExecutionTask.from_json(task_data)
                self.idempotency_storage.update_state(task.run_id, TaskState.FAILED, str(e))
            except Exception:
                self.logger.exception("Could not update idempotency state for failed task")

    async def _execute_step(self, task: OpExecutionTask) -> None:
        """Execute a Dagster step."""
        from dagster import DagsterInstance
        from dagster._core.definitions.reconstruct import ReconstructableJob
        from dagster._core.execution.api import create_execution_plan, execute_plan_iterator
        from dagster._serdes import unpack_value
        from dagster._grpc.types import ExecuteStepArgs

        # Reconstruct the instance
        instance = DagsterInstance.from_ref(unpack_value(task.instance_ref_dict))

        # Reconstruct the job
        recon_job = ReconstructableJob.from_dict(task.reconstructable_job_dict)

        # Get the run
        dagster_run = instance.get_run_by_id(task.run_id)
        if not dagster_run:
            raise ValueError(f"Could not load run {task.run_id}")

        # Create execution plan
        execution_plan = create_execution_plan(
            recon_job,
            dagster_run.run_config,
            step_keys_to_execute=task.step_keys_to_execute,
            known_state=unpack_value(task.known_state_dict) if task.known_state_dict else None,
        )

        # Execute the plan
        step_keys_str = ", ".join(task.step_keys_to_execute)
        self.logger.info("Executing steps %s in TaskIQ worker", step_keys_str)

        # Report engine event
        engine_event = instance.report_engine_event(
            f"Executing steps {step_keys_str} in TaskIQ worker",
            dagster_run,
            None,  # EngineEventData
            None,  # executor
        )

        # Execute and collect events
        events = [engine_event]
        for step_event in execute_plan_iterator(
            execution_plan=execution_plan,
            job=recon_job,
            dagster_run=dagster_run,
            instance=instance,
            retry_mode=unpack_value(task.retry_mode_dict),
            run_config=dagster_run.run_config,
        ):
            events.append(step_event)

        self.logger.info("Completed execution of steps %s", step_keys_str)