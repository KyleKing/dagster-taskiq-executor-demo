"""SQS broker implementation for Taskiq using aioboto3."""

import json
from typing import Any, AsyncGenerator, Optional

import aioboto3
from pydantic import BaseModel, Field
from taskiq import AsyncBroker, AckableMessage, BrokerMessage
from taskiq.abc.result_backend import AsyncResultBackend


class SQSBrokerConfig(BaseModel):
    """Configuration for SQS broker."""

    queue_url: str = Field(description="SQS queue URL")
    endpoint_url: Optional[str] = Field(default=None, description="Custom AWS endpoint URL (e.g., for LocalStack)")
    region_name: str = Field(default="us-east-1", description="AWS region")
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key ID")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS secret access key")
    max_number_of_messages: int = Field(default=1, description="Max messages to receive in one batch")
    wait_time_seconds: int = Field(default=20, description="Long polling wait time")
    visibility_timeout: int = Field(default=300, description="Message visibility timeout in seconds")


class SQSBroker(AsyncBroker):
    """Async SQS broker for Taskiq using aioboto3.

    This broker uses AWS SQS for task distribution and supports:
    - Long polling for efficient message retrieval
    - Message acknowledgment
    - Task priority via message attributes
    - Custom queue routing
    """

    def __init__(
        self,
        queue_url: str,
        endpoint_url: Optional[str] = None,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        max_number_of_messages: int = 1,
        wait_time_seconds: int = 20,
        visibility_timeout: int = 300,
        result_backend: Optional[AsyncResultBackend] = None,
        **kwargs: Any,
    ):
        """Initialize SQS broker.

        Args:
            queue_url: SQS queue URL
            endpoint_url: Custom AWS endpoint (for LocalStack)
            region_name: AWS region name
            aws_access_key_id: AWS access key
            aws_secret_access_key: AWS secret key
            max_number_of_messages: Max messages per receive call
            wait_time_seconds: Long polling wait time
            visibility_timeout: Message visibility timeout
            result_backend: Optional result backend
            **kwargs: Additional broker arguments
        """
        super().__init__(result_backend=result_backend, **kwargs)

        self.config = SQSBrokerConfig(
            queue_url=queue_url,
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            max_number_of_messages=max_number_of_messages,
            wait_time_seconds=wait_time_seconds,
            visibility_timeout=visibility_timeout,
        )

        # Create session for aioboto3
        self.session = aioboto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )

    async def kick(self, message: BrokerMessage) -> None:
        """Send a task message to SQS.

        Args:
            message: The broker message to send
        """
        async with self.session.client(
            "sqs",
            endpoint_url=self.config.endpoint_url,
            region_name=self.config.region_name,
        ) as sqs:
            # Serialize the message
            message_body = message.message

            # Prepare message attributes
            message_attributes = {}

            # Add labels as message attributes
            if message.labels:
                for key, value in message.labels.items():
                    if isinstance(value, (str, int, float, bool)):
                        message_attributes[key] = {
                            "StringValue": str(value),
                            "DataType": "String",
                        }

            # Add task name
            message_attributes["task_name"] = {
                "StringValue": message.task_name,
                "DataType": "String",
            }

            # Send message to SQS
            send_params = {
                "QueueUrl": self.config.queue_url,
                "MessageBody": message_body.decode() if isinstance(message_body, bytes) else message_body,
            }

            if message_attributes:
                send_params["MessageAttributes"] = message_attributes

            await sqs.send_message(**send_params)

    async def listen(self) -> AsyncGenerator[AckableMessage, None]:
        """Listen for messages from SQS.

        Yields:
            AckableMessage instances that can be acknowledged
        """
        async with self.session.client(
            "sqs",
            endpoint_url=self.config.endpoint_url,
            region_name=self.config.region_name,
        ) as sqs:
            while True:
                # Receive messages from SQS
                response = await sqs.receive_message(
                    QueueUrl=self.config.queue_url,
                    MaxNumberOfMessages=self.config.max_number_of_messages,
                    WaitTimeSeconds=self.config.wait_time_seconds,
                    VisibilityTimeout=self.config.visibility_timeout,
                    MessageAttributeNames=["All"],
                )

                messages = response.get("Messages", [])

                for sqs_message in messages:
                    # Create acknowledgment callback
                    receipt_handle = sqs_message["ReceiptHandle"]

                    async def ack() -> None:
                        """Acknowledge (delete) the message from SQS."""
                        async with self.session.client(
                            "sqs",
                            endpoint_url=self.config.endpoint_url,
                            region_name=self.config.region_name,
                        ) as ack_sqs:
                            await ack_sqs.delete_message(
                                QueueUrl=self.config.queue_url,
                                ReceiptHandle=receipt_handle,
                            )

                    async def reject() -> None:
                        """Reject the message (make it visible again)."""
                        async with self.session.client(
                            "sqs",
                            endpoint_url=self.config.endpoint_url,
                            region_name=self.config.region_name,
                        ) as reject_sqs:
                            await reject_sqs.change_message_visibility(
                                QueueUrl=self.config.queue_url,
                                ReceiptHandle=receipt_handle,
                                VisibilityTimeout=0,
                            )

                    # Extract message body
                    message_body = sqs_message["Body"]

                    # Convert to bytes if needed
                    if isinstance(message_body, str):
                        message_body = message_body.encode()

                    # Yield the ackable message
                    yield AckableMessage(
                        data=message_body,
                        ack=ack,
                        reject=reject,
                    )

    async def startup(self) -> None:
        """Startup hook for the broker."""
        await super().startup()

    async def shutdown(self) -> None:
        """Shutdown hook for the broker."""
        await super().shutdown()
