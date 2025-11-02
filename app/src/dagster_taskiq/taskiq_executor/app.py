"""TaskIQ application for executing Dagster ops from SQS messages."""

import asyncio
import json
import logging
from datetime import UTC, datetime

import aioboto3

from dagster_taskiq.config.settings import Settings
from dagster_taskiq.taskiq_executor.models import get_idempotency_storage
from dagster_taskiq.taskiq_executor.task_payloads import ExecutionResult, OpExecutionTask, TaskState


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
            self.logger.info("Processing task for step %s in run %s", task.step_key, task.run_id)

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
        """Execute a Dagster step and return the result."""
        started_at = datetime.now(UTC)

        try:
            # TODO: Implement proper step execution using Dagster APIs
            # For now, we'll simulate execution since full reconstruction is complex
            self.logger.info("Simulating execution of step %s for run %s", task.step_key, task.run_id)

            # Simulate some work
            await asyncio.sleep(1.0)

            # Mock successful result
            completed_at = datetime.now(UTC)
            execution_time = (completed_at - started_at).total_seconds()

            return ExecutionResult(
                run_id=task.run_id,
                step_key=task.step_key,
                state=TaskState.COMPLETED,
                output={"mock_output": "success"},
                started_at=started_at,
                completed_at=completed_at,
                execution_time_seconds=execution_time,
            )

        except Exception as e:
            self.logger.exception("Error executing step %s: %s", task.step_key, e)
            completed_at = datetime.now(UTC)
            execution_time = (completed_at - started_at).total_seconds()

            return ExecutionResult(
                run_id=task.run_id,
                step_key=task.step_key,
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
