# Modifications copyright (c) 2024 dagster-taskiq contributors

"""SQS broker wrapper using aioboto3."""

import asyncio
import json
import logging
from typing import Any

import aioboto3


class SqsBroker:
    """SQS broker with retry logic and structured logging."""

    def __init__(
        self,
        queue_url: str,
        aws_endpoint_url: str | None = None,
        aws_region: str = "us-east-1",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
    ) -> None:
        """Initialize SQS broker."""
        self.queue_url = queue_url
        self.aws_endpoint_url = aws_endpoint_url
        self.aws_region = aws_region
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.logger = logging.getLogger(__name__)
        self.sqs_client: Any = None

    async def startup(self) -> None:
        """Start the broker."""
        self.logger.info("Starting SQS broker for queue: %s", self.queue_url)

        try:
            # Create SQS client
            self.sqs_client = aioboto3.client(  # type: ignore[attr-defined]
                "sqs",
                endpoint_url=self.aws_endpoint_url,
                region_name=self.aws_region,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )

            self.logger.info("SQS broker started successfully")

        except Exception as e:
            self.logger.exception("Failed to start SQS broker: %s", e)
            raise

    def startup_sync(self) -> None:
        """Synchronous startup for use in Dagster executor."""
        asyncio.run(self.startup())

    async def shutdown(self) -> None:
        """Shutdown the broker."""
        self.logger.info("Shutting down SQS broker")
        if self.sqs_client:
            await self.sqs_client.close()  # type: ignore[attr-defined]
        self.logger.info("SQS broker shut down successfully")

    def shutdown_sync(self) -> None:
        """Synchronous shutdown for use in Dagster executor."""
        asyncio.run(self.shutdown())

    async def send_message(self, message: Any) -> None:
        """Send a message with enhanced error handling."""
        if not self.sqs_client:
            raise RuntimeError("Broker not started")

        try:
            # Convert message to string if it's not already
            if not isinstance(message, str):
                message = json.dumps(message)

            await self.sqs_client.send_message(  # type: ignore[attr-defined]
                QueueUrl=self.queue_url,
                MessageBody=message,
            )
            self.logger.debug("Message sent to queue: %s", self.queue_url)
        except Exception as e:
            self.logger.exception("Failed to send message to queue: %s", e)
            raise

    def send_message_sync(self, message: Any) -> None:
        """Synchronous message sending for use in Dagster executor."""
        asyncio.run(self.send_message(message))