# Modifications copyright (c) 2024 dagster-taskiq contributors

"""Cancellable SQS broker implementation with SQS-based task cancellation."""

import uuid
from typing import AsyncGenerator

import aioboto3

from taskiq.message import TaskiqMessage

from .broker import create_sqs_broker


class CancellableSQSBroker:
    """SQS broker with SQS-based cancellation support."""

    def __init__(self, *args, cancel_queue_url: str | None = None, **kwargs):
        self.sqs_broker = create_sqs_broker(*args, **kwargs)
        self.cancel_queue_url = cancel_queue_url or self.sqs_broker.queue_url.replace("dagster-tasks", "dagster-cancels")  # Default cancel queue
        self.cancel_sqs_client = None

    async def startup(self):
        await self.sqs_broker.startup()
        # Setup SQS client for cancel queue
        self.cancel_sqs_client = aioboto3.client(
            "sqs",
            endpoint_url=self.sqs_broker.endpoint_url,
            region_name=self.sqs_broker.region_name,
            aws_access_key_id=self.sqs_broker.aws_access_key_id,
            aws_secret_access_key=self.sqs_broker.aws_secret_access_key,
        )

    async def shutdown(self):
        await self.sqs_broker.shutdown()
        if self.cancel_sqs_client:
            await self.cancel_sqs_client.close()

    async def cancel_task(self, task_id: uuid.UUID) -> None:
        """Send a cancellation message to the cancel queue."""
        if not self.cancel_sqs_client:
            return

        taskiq_message = TaskiqMessage(
            task_id=self.sqs_broker.id_generator(),  # Generate new id for cancel message
            task_name="canceller",
            labels={},
            labels_types={},
            args=[],
            kwargs={"__cancel_task_id__": str(task_id)},
        )
        broker_message = self.sqs_broker.formatter.dumps(taskiq_message)
        await self.cancel_sqs_client.send_message(
            QueueUrl=self.cancel_queue_url,
            MessageBody=broker_message.message,
        )

    async def listen_canceller(self) -> AsyncGenerator[bytes, None]:
        """Poll for cancellation messages from the cancel queue."""
        if not self.cancel_sqs_client:
            return

        while True:
            response = await self.cancel_sqs_client.receive_message(
                QueueUrl=self.cancel_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1,  # Short poll for responsiveness
            )
            messages = response.get("Messages", [])
            if messages:
                message = messages[0]
                receipt_handle = message["ReceiptHandle"]
                body = message["Body"]
                yield body
                # Delete the message after processing
                await self.cancel_sqs_client.delete_message(
                    QueueUrl=self.cancel_queue_url,
                    ReceiptHandle=receipt_handle,
                )
            else:
                # No message, continue polling
                continue

    # Delegate other methods to sqs_broker
    def __getattr__(self, name):
        return getattr(self.sqs_broker, name)</content>
<parameter name="filePath">/Users/kyleking/Developer/kyleking/dagster-taskiq-executor-demo/dagster-celery-to-taskiq/src/dagster_taskiq/cancellable_broker.py