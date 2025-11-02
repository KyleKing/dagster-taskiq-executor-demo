"""TaskIQ application for executing Dagster ops from SQS messages."""

import asyncio
import json
import logging
from datetime import UTC, datetime

import aioboto3

from dagster_taskiq_demo.config.settings import Settings
from dagster_taskiq_demo.taskiq_executor.models import get_idempotency_storage
from dagster_taskiq_demo.taskiq_executor.task_payloads import ExecutionResult, OpExecutionTask, TaskState


class DagsterTaskiqApp:
    """TaskIQ application for processing Dagster op execution tasks."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the TaskIQ application."""
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.idempotency_storage = get_idempotency_storage()
        self.health_server: asyncio.Server | None = None
        self.running = False

        # Create SQS client
        self.sqs_client = aioboto3.client(
            "sqs",
            endpoint_url=settings.aws_endpoint_url,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    async def _execute_op_task(self, task_data: str) -> None:
        """Execute a single op task."""
        try:
            # Parse task
            task = OpExecutionTask.from_json(task_data)
            step_keys_str = ", ".join(task.step_keys_to_execute)
            self.logger.info("Processing task for steps %s in run %s", step_keys_str, task.run_id)

            # Check idempotency - if already completed, skip
            if self.idempotency_storage.is_completed(task.idempotency_key):
                self.logger.info("Task %s already completed, skipping", task.idempotency_key)
                return

            # Mark as running
            self.idempotency_storage.update_state(task.idempotency_key, TaskState.RUNNING)

            # Execute the step
            result = await self._execute_step(task)

            # Update idempotency with result
            self.idempotency_storage.update_state(task.idempotency_key, result.state, result.to_json())

            self.logger.info("Task %s completed with state %s", task.idempotency_key, result.state)

        except Exception as e:
            self.logger.exception("Error executing op task: %s", e)
            # Try to extract idempotency key from task data for error reporting
            try:
                task = OpExecutionTask.from_json(task_data)
                self.idempotency_storage.update_state(task.idempotency_key, TaskState.FAILED, str(e))
            except Exception:
                self.logger.exception("Could not update idempotency state for failed task")

    async def _execute_step(self, task: OpExecutionTask) -> ExecutionResult:
        """Execute a Dagster step."""
        from dagster import DagsterInstance
        from dagster._core.definitions.reconstruct import ReconstructableJob
        from dagster._core.execution.api import create_execution_plan, execute_plan_iterator
        from dagster._serdes import unpack_value

        started_at = datetime.now(UTC)

        try:
            # Reconstruct the instance
            instance = DagsterInstance.from_ref(unpack_value(task.instance_ref_dict))

            # Reconstruct the job
            recon_job = ReconstructableJob.from_dict(task.reconstructable_job_dict)

            # Get the run
            dagster_run = instance.get_run_by_id(task.run_id)
            if not dagster_run:
                msg = f"Could not load run {task.run_id}"
                raise ValueError(msg)

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

            completed_at = datetime.now(UTC)
            execution_time = (completed_at - started_at).total_seconds()

            self.logger.info("Completed execution of steps %s", step_keys_str)

            return ExecutionResult(
                run_id=task.run_id,
                step_keys=task.step_keys_to_execute,
                state=TaskState.COMPLETED,
                output={"events": [event.to_dict() for event in events]},
                started_at=started_at,
                completed_at=completed_at,
                execution_time_seconds=execution_time,
            )

        except Exception as e:
            self.logger.exception("Error executing steps %s: %s", ", ".join(task.step_keys_to_execute), e)
            completed_at = datetime.now(UTC)
            execution_time = (completed_at - started_at).total_seconds()

            return ExecutionResult(
                run_id=task.run_id,
                step_keys=task.step_keys_to_execute,
                state=TaskState.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=completed_at,
                execution_time_seconds=execution_time,
            )

    async def startup(self) -> None:
        """Start the TaskIQ application."""
        self.logger.info("Starting TaskIQ worker application")
        self.running = True
        await self._start_health_server()

    async def shutdown(self) -> None:
        """Shutdown the TaskIQ application."""
        self.logger.info("Shutting down TaskIQ worker application")
        self.running = False
        await self._stop_health_server()

    async def _start_health_server(self) -> None:
        """Start the health check HTTP server."""
        try:
            self.health_server = await asyncio.start_server(
                self._handle_health_request,
                host="0.0.0.0",
                port=self.settings.taskiq_worker_health_port,
            )
            self.logger.info("Health server started on port %d", self.settings.taskiq_worker_health_port)
        except Exception as e:
            self.logger.exception("Failed to start health server: %s", e)
            raise

    async def _stop_health_server(self) -> None:
        """Stop the health check HTTP server."""
        if self.health_server:
            self.health_server.close()
            await self.health_server.wait_closed()
            self.logger.info("Health server stopped")

    async def _handle_health_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming health check requests."""
        try:
            # Read the request line
            request_line = await reader.readline()
            if not request_line:
                return

            # Parse request (simple HTTP/1.0 parsing)
            parts = request_line.decode().strip().split()
            if len(parts) >= 2 and parts[0] == "GET" and parts[1] in {"/health", "/health/"}:
                # Send health response
                response = json.dumps({"status": "healthy", "service": "taskiq-worker"}).encode()
                writer.write(b"HTTP/1.0 200 OK\r\n")
                writer.write(b"Content-Type: application/json\r\n")
                writer.write(f"Content-Length: {len(response)}\r\n".encode())
                writer.write(b"\r\n")
                writer.write(response)
            else:
                # Not found
                writer.write(b"HTTP/1.0 404 Not Found\r\n")
                writer.write(b"Content-Length: 0\r\n")
                writer.write(b"\r\n")

        except Exception as e:
            self.logger.exception("Error handling health request: %s", e)
        finally:
            writer.close()
            await writer.wait_closed()

    def run_worker(self) -> None:
        """Run the TaskIQ worker."""
        asyncio.run(self._run_worker_async())

    async def _run_worker_async(self) -> None:
        """Run the TaskIQ worker asynchronously."""
        try:
            await self.startup()
            # Run the worker loop
            await self._run_worker_loop()
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        finally:
            await self.shutdown()

    async def _run_worker_loop(self) -> None:
        """Run the main worker loop to consume SQS messages."""
        self.logger.info("Starting worker loop for queue: %s", self.settings.taskiq_queue_name)

        while self.running:
            try:
                # Receive messages from SQS
                response = await self.sqs_client.receive_message(
                    QueueUrl=self._get_queue_url(),
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,  # Long polling
                    VisibilityTimeout=self.settings.taskiq_visibility_timeout,
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
                    QueueUrl=self._get_queue_url(),
                    ReceiptHandle=receipt_handle,
                )
                self.logger.debug("Message processed and deleted")

            except Exception as e:
                self.logger.exception("Error in worker loop: %s", e)
                await asyncio.sleep(5)  # Back off on errors

    def _get_queue_url(self) -> str:
        """Get the SQS queue URL."""
        # For LocalStack, construct the URL
        return f"{self.settings.aws_endpoint_url}/000000000000/{self.settings.taskiq_queue_name}"


# Global app instance
settings = Settings()
taskiq_app = DagsterTaskiqApp(settings)
