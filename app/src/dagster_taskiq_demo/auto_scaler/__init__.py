"""Auto-scaling service for TaskIQ workers."""

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import aioboto3

from dagster_taskiq_demo.config.settings import Settings


@dataclass
class QueueMetrics:
    """Queue metrics from SQS."""

    visible_messages: int
    not_visible_messages: int
    oldest_message_age_seconds: Optional[int]
    timestamp: datetime


@dataclass
class ScalingDecision:
    """Scaling decision result."""

    action: str  # "scale_up", "scale_down", "no_action"
    target_count: int
    reason: str


class AutoScalerService:
    """Auto-scaling service for TaskIQ workers."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the auto-scaler service."""
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.health_server: Optional[asyncio.Server] = None
        self.last_scale_time = 0.0
        self.current_worker_count = settings.autoscaler_min_workers

        # Create AWS clients
        self.sqs_client = aioboto3.client(  # type: ignore[attr-defined]
            "sqs",
            endpoint_url=settings.aws_endpoint_url,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.ecs_client = aioboto3.client(  # type: ignore[attr-defined]
            "ecs",
            endpoint_url=settings.aws_endpoint_url,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    async def startup(self) -> None:
        """Start the auto-scaler service."""
        self.logger.info("Starting auto-scaler service")
        self.running = True
        await self._start_health_server()

    async def shutdown(self) -> None:
        """Shutdown the auto-scaler service."""
        self.logger.info("Shutting down auto-scaler service")
        self.running = False
        await self._stop_health_server()

    async def _start_health_server(self) -> None:
        """Start the health check HTTP server."""
        try:
            self.health_server = await asyncio.start_server(
                self._handle_health_request,
                host="0.0.0.0",
                port=8081,  # Different port from worker
            )
            self.logger.info("Auto-scaler health server started on port 8081")
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
            request_line = await reader.readline()
            if not request_line:
                return

            parts = request_line.decode().strip().split()
            if len(parts) >= 2 and parts[0] == "GET" and parts[1] in {"/health", "/health/", "/healthz", "/healthz/"}:
                response = json.dumps({"status": "healthy", "service": "auto-scaler"}).encode()
                writer.write(b"HTTP/1.0 200 OK\r\n")
                writer.write(b"Content-Type: application/json\r\n")
                writer.write(f"Content-Length: {len(response)}\r\n".encode())
                writer.write(b"\r\n")
                writer.write(response)
            else:
                writer.write(b"HTTP/1.0 404 Not Found\r\n")
                writer.write(b"Content-Length: 0\r\n")
                writer.write(b"\r\n")

        except Exception as e:
            self.logger.exception("Error handling health request: %s", e)
        finally:
            writer.close()
            await writer.wait_closed()

    async def get_queue_metrics(self) -> QueueMetrics:
        """Get current queue metrics from SQS."""
        try:
            response = await self.sqs_client.get_queue_attributes(
                QueueUrl=self._get_queue_url(),
                AttributeNames=[
                    "ApproximateNumberOfMessages",
                    "ApproximateNumberOfMessagesNotVisible",
                    "ApproximateAgeOfOldestMessage",
                ],
            )

            attributes = response["Attributes"]
            return QueueMetrics(
                visible_messages=int(attributes["ApproximateNumberOfMessages"]),
                not_visible_messages=int(attributes["ApproximateNumberOfMessagesNotVisible"]),
                oldest_message_age_seconds=int(attributes.get("ApproximateAgeOfOldestMessage", 0)) or None,
                timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            self.logger.exception("Failed to get queue metrics: %s", e)
            # Return zero metrics on error
            return QueueMetrics(0, 0, None, datetime.now(timezone.utc))

    def calculate_scaling_decision(self, metrics: QueueMetrics) -> ScalingDecision:
        """Calculate scaling decision based on queue metrics."""
        current_time = time.time()

        # Check cooldown
        if current_time - self.last_scale_time < self.settings.autoscaler_cooldown_seconds:
            return ScalingDecision("no_action", self.current_worker_count, "cooldown active")

        # Scale up logic
        scale_up_threshold = self.current_worker_count * self.settings.autoscaler_scale_up_threshold
        if metrics.visible_messages > scale_up_threshold:
            new_count = min(self.current_worker_count + 1, self.settings.autoscaler_max_workers)
            if new_count > self.current_worker_count:
                return ScalingDecision("scale_up", new_count, f"visible messages ({metrics.visible_messages}) > threshold ({scale_up_threshold})")

        # Scale down logic
        scale_down_threshold = self.current_worker_count * self.settings.autoscaler_scale_down_threshold
        if metrics.visible_messages < scale_down_threshold and self.current_worker_count > self.settings.autoscaler_min_workers:
            new_count = max(self.current_worker_count - 1, self.settings.autoscaler_min_workers)
            if new_count < self.current_worker_count:
                return ScalingDecision("scale_down", new_count, f"visible messages ({metrics.visible_messages}) < threshold ({scale_down_threshold})")

        return ScalingDecision("no_action", self.current_worker_count, "within thresholds")

    async def execute_scaling_action(self, decision: ScalingDecision) -> None:
        """Execute the scaling action."""
        if decision.action == "no_action":
            return

        try:
            self.logger.info("Executing scaling action: %s to %d workers (%s)",
                           decision.action, decision.target_count, decision.reason)

            # Update ECS service
            await self.ecs_client.update_service(
                cluster=self.settings.ecs_cluster_name,
                service=self.settings.ecs_worker_service_name,
                desiredCount=decision.target_count,
            )

            self.current_worker_count = decision.target_count
            self.last_scale_time = time.time()

            self.logger.info("Scaling action completed successfully")

        except Exception as e:
            self.logger.exception("Failed to execute scaling action: %s", e)

    async def simulate_worker_crash(self) -> None:
        """Simulate a worker task crash by stopping a random task."""
        try:
            # List running tasks
            response = await self.ecs_client.list_tasks(
                cluster=self.settings.ecs_cluster_name,
                serviceName=self.settings.ecs_worker_service_name,
                desiredStatus="RUNNING",
            )

            tasks = response.get("taskArns", [])
            if not tasks:
                self.logger.info("No running tasks to crash")
                return

            # Pick a random task to stop
            task_to_stop = random.choice(tasks)
            self.logger.info("Simulating worker crash: stopping task %s", task_to_stop)

            await self.ecs_client.stop_task(
                cluster=self.settings.ecs_cluster_name,
                task=task_to_stop,
                reason="Simulated failure for testing",
            )

            self.logger.info("Worker crash simulation completed")

        except Exception as e:
            self.logger.exception("Failed to simulate worker crash: %s", e)

    async def simulate_drain_and_restart(self) -> None:
        """Simulate draining all workers and restarting."""
        try:
            self.logger.info("Simulating drain and restart: scaling to 0 workers")

            # Scale to 0
            await self.ecs_client.update_service(
                cluster=self.settings.ecs_cluster_name,
                service=self.settings.ecs_worker_service_name,
                desiredCount=0,
            )

            # Wait for drain (simulate)
            await asyncio.sleep(30)  # Wait 30 seconds

            # Scale back to minimum
            self.logger.info("Restarting workers to minimum count: %d", self.settings.autoscaler_min_workers)
            await self.ecs_client.update_service(
                cluster=self.settings.ecs_cluster_name,
                service=self.settings.ecs_worker_service_name,
                desiredCount=self.settings.autoscaler_min_workers,
            )

            self.current_worker_count = self.settings.autoscaler_min_workers
            self.logger.info("Drain and restart simulation completed")

        except Exception as e:
            self.logger.exception("Failed to simulate drain and restart: %s", e)

    async def simulate_network_partition(self) -> None:
        """Simulate network partition by temporarily disabling message processing."""
        try:
            self.logger.info("Simulating network partition: pausing message processing")

            # For LocalStack simulation, we'll just pause the control loop briefly
            # In a real AWS environment, this might involve security group changes
            await asyncio.sleep(60)  # Simulate 1 minute partition

            self.logger.info("Network partition simulation completed")

        except Exception as e:
            self.logger.exception("Failed to simulate network partition: %s", e)

    async def simulate_failure(self) -> None:
        """Simulate a random failure for testing."""
        failure_types = ["worker_crash", "drain_restart", "network_partition"]
        failure_type = random.choice(failure_types)

        self.logger.info("Simulating random failure: %s", failure_type)

        if failure_type == "worker_crash":
            await self.simulate_worker_crash()
        elif failure_type == "drain_restart":
            await self.simulate_drain_and_restart()
        elif failure_type == "network_partition":
            await self.simulate_network_partition()

    async def run_control_loop(self) -> None:
        """Run the main auto-scaling control loop."""
        self.logger.info("Starting auto-scaler control loop")

        while self.running:
            try:
                # Get queue metrics
                metrics = await self.get_queue_metrics()
                self.logger.info("Queue metrics: visible=%d, not_visible=%d, oldest_age=%s",
                               metrics.visible_messages, metrics.not_visible_messages,
                               f"{metrics.oldest_message_age_seconds}s" if metrics.oldest_message_age_seconds else "unknown")

                # Emit structured metrics (could be scraped by monitoring systems)
                self._emit_metrics(metrics)

                # Calculate scaling decision
                decision = self.calculate_scaling_decision(metrics)

                # Execute scaling if needed
                await self.execute_scaling_action(decision)

                # Simulate failures periodically (configurable)
                # TODO: Add settings for failure simulation enable/disable and probability
                if random.random() < 0.05:  # 5% chance per cycle for testing
                    await self.simulate_failure()

                # Wait for next cycle
                await asyncio.sleep(self.settings.autoscaler_cooldown_seconds)

            except Exception as e:
                self.logger.exception("Error in control loop: %s", e)
                await asyncio.sleep(10)  # Back off on errors

    def _emit_metrics(self, metrics: QueueMetrics) -> None:
        """Emit metrics for monitoring systems."""
        # Log structured metrics that could be parsed by log aggregation systems
        # In production, this might send to CloudWatch or Prometheus
        self.logger.info(
            "METRICS queue_depth_visible=%d queue_depth_not_visible=%d queue_oldest_age_seconds=%s current_workers=%d",
            metrics.visible_messages,
            metrics.not_visible_messages,
            metrics.oldest_message_age_seconds or 0,
            self.current_worker_count,
        )

        # Alert if queue is getting too old
        if metrics.oldest_message_age_seconds and metrics.oldest_message_age_seconds > 300:  # 5 minutes
            self.logger.warning("ALERT: Queue oldest message age (%ds) exceeds threshold (300s)",
                              metrics.oldest_message_age_seconds)

    def _get_queue_url(self) -> str:
        """Get the SQS queue URL."""
        return f"{self.settings.aws_endpoint_url}/000000000000/{self.settings.taskiq_queue_name}"

    def run_service(self) -> None:
        """Run the auto-scaler service."""
        asyncio.run(self._run_service_async())

    async def _run_service_async(self) -> None:
        """Run the auto-scaler service asynchronously."""
        try:
            await self.startup()
            await self.run_control_loop()
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        finally:
            await self.shutdown()


# Global settings instance
settings = Settings()
