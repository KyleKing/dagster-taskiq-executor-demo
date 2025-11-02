"""LocalStack-aware SQS broker wrapper using aioboto3."""

import asyncio
import json
import logging
from typing import Any

import aioboto3

from dagster_taskiq.config.settings import Settings


class LocalStackSqsBroker:
    """SQS broker configured for LocalStack with retry logic and structured logging."""

    def __init__(self, settings: Settings) -> None:
        """Initialize LocalStack SQS broker."""
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.sqs_client: Any = None
        self.queue_url: str | None = None

    async def startup(self) -> None:
        """Start the broker."""
        self.logger.info("Starting LocalStack SQS broker for queue: %s", self.settings.taskiq_queue_name)

        try:
            # Create SQS client
            self.sqs_client = aioboto3.client(  # type: ignore[attr-defined]
                "sqs",
                endpoint_url=self.settings.aws_endpoint_url,
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            )

            # Get queue URL
            response = await self.sqs_client.get_queue_url(QueueName=self.settings.taskiq_queue_name)  # type: ignore[attr-defined]
            self.queue_url = response["QueueUrl"]

            self.logger.info("LocalStack SQS broker started successfully")

        except Exception as e:
            self.logger.exception("Failed to start LocalStack SQS broker: %s", e)
            raise

    def startup_sync(self) -> None:
        """Synchronous startup for use in Dagster executor."""
        asyncio.run(self.startup())

    async def shutdown(self) -> None:
        """Shutdown the broker."""
        self.logger.info("Shutting down LocalStack SQS broker")
        if self.sqs_client:
            await self.sqs_client.close()  # type: ignore[attr-defined]
        self.logger.info("LocalStack SQS broker shut down successfully")

    def shutdown_sync(self) -> None:
        """Synchronous shutdown for use in Dagster executor."""
        asyncio.run(self.shutdown())

    async def kick(self, message: Any) -> None:
        """Send a message with enhanced error handling."""
        if not self.sqs_client or not self.queue_url:
            raise RuntimeError("Broker not started")

        try:
            # Convert message to string if it's not already
            if not isinstance(message, str):
                message = json.dumps(message)

            await self.sqs_client.send_message(  # type: ignore[attr-defined]
                QueueUrl=self.queue_url,
                MessageBody=message,
            )
            self.logger.debug("Message sent to queue: %s", self.settings.taskiq_queue_name)
        except Exception as e:
            self.logger.exception("Failed to send message to queue: %s", e)
            raise

    def kick_sync(self, message: Any) -> None:
        """Synchronous message sending for use in Dagster executor."""
        asyncio.run(self.kick(message))
