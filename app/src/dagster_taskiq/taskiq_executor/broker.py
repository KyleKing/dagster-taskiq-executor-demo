"""LocalStack-aware SQS broker wrapper for TaskIQ."""

import logging
from typing import Any

from taskiq_aio_sqs import SQSBroker as SqsAsyncBroker

from dagster_taskiq.config.settings import Settings


class LocalStackSqsBroker(SqsAsyncBroker):
    """SQS broker configured for LocalStack with retry logic and structured logging."""

    def __init__(self, settings: Settings) -> None:
        """Initialize LocalStack SQS broker."""
        self.settings = settings
        self.logger = logging.getLogger(__name__)

        super().__init__(
            endpoint_url=settings.aws_endpoint_url,
            sqs_queue_name=settings.taskiq_queue_name,
        )

    async def startup(self) -> None:
        """Start the broker."""
        self.logger.info("Starting LocalStack SQS broker for queue: %s", self.settings.taskiq_queue_name)

        try:
            # Call parent startup
            await super().startup()
            self.logger.info("LocalStack SQS broker started successfully")

        except Exception as e:
            self.logger.exception("Failed to start LocalStack SQS broker: %s", e)
            raise

    def startup_sync(self) -> None:
        """Synchronous startup for use in Dagster executor."""
        import asyncio
        asyncio.run(self.startup())

    async def shutdown(self) -> None:
        """Shutdown the broker."""
        self.logger.info("Shutting down LocalStack SQS broker")
        try:
            await super().shutdown()
            self.logger.info("LocalStack SQS broker shut down successfully")
        except Exception as e:
            self.logger.exception("Error during broker shutdown: %s", e)
            raise

    def shutdown_sync(self) -> None:
        """Synchronous shutdown for use in Dagster executor."""
        import asyncio
        asyncio.run(self.shutdown())

    async def kick(self, message: Any) -> None:
        """Send a message with enhanced error handling."""
        try:
            await super().kick(message)
            self.logger.debug("Message sent to queue: %s", self.settings.taskiq_queue_name)
        except Exception as e:
            self.logger.exception("Failed to send message to queue: %s", e)
            raise

    def kick_sync(self, message: Any) -> None:
        """Synchronous message sending for use in Dagster executor."""
        import asyncio
        asyncio.run(self.kick(message))
