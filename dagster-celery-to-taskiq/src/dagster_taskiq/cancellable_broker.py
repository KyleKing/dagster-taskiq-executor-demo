# Modifications copyright (c) 2024 dagster-taskiq contributors

"""
Cancellable SQS broker implementation with SQS-based task cancellation.

DESIGN NOTES:
- Uses separate SQS queue for cancellation messages to avoid Redis dependency
- Workers poll cancel queue alongside main task queue
- Cancellation messages contain task_id to identify which task to cancel
- Implements at-least-once delivery semantics for cancellation
- Future enhancement: Integrate with taskiq-aio-sqs native cancellation features

ARCHITECTURE:
1. Main task queue: dagster-tasks (for job execution)
2. Cancel queue: dagster-cancels (for cancellation signals)
3. Workers listen to both queues simultaneously
4. Cancellation is cooperative - workers check cancel queue periodically

TODO: Implement worker-side cancellation checking in core_execution_loop.py
"""

import uuid
from typing import AsyncGenerator, Optional

import aioboto3

from taskiq import AsyncBroker
from taskiq.message import TaskiqMessage

from .broker import SqsBrokerConfig


class CancellableSQSBroker(AsyncBroker):
    """SQS broker with SQS-based cancellation support."""

    def __init__(
        self,
        broker_config: SqsBrokerConfig,
        *,
        result_backend: Optional[object] = None,
        cancel_queue_url: str | None = None,
    ):
        super().__init__()
        self._config = broker_config
        self.sqs_broker = broker_config.create_broker(result_backend=result_backend)
        self.cancel_queue_url = cancel_queue_url or _derive_cancel_queue_url(broker_config.queue_url)
        self.cancel_sqs_client = None
        self._cancel_client_cm = None
        self.supports_cancellation = True

    async def startup(self):
        await self.sqs_broker.startup()
        # Setup SQS client for cancel queue
        if self.cancel_sqs_client:
            return

        session = aioboto3.Session()
        client_cm = session.client(
            "sqs",
            endpoint_url=self._config.endpoint_url,
            region_name=self._config.region_name,
            aws_access_key_id=self._config.aws_access_key_id,
            aws_secret_access_key=self._config.aws_secret_access_key,
        )
        self._cancel_client_cm = client_cm
        self.cancel_sqs_client = await client_cm.__aenter__()

    async def shutdown(self):
        await self.sqs_broker.shutdown()
        if self._cancel_client_cm is not None:
            await self._cancel_client_cm.__aexit__(None, None, None)
            self._cancel_client_cm = None
            self.cancel_sqs_client = None

    async def cancel_task(self, task_id: uuid.UUID) -> None:
        """Send a cancellation message to the cancel queue."""
        if not self.cancel_sqs_client:
            await self.startup()
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
            await self.startup()
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
        return getattr(self.sqs_broker, name)

    async def kick(self, task):
        return await self.sqs_broker.kick(task)

    async def listen(self):
        async for message in self.sqs_broker.listen():
            yield message


def _derive_cancel_queue_url(queue_url: str) -> str:
    if not queue_url:
        raise ValueError('Cannot derive cancel queue URL without a base queue URL')
    queue_url = queue_url.rstrip('/')
    prefix, _, queue_name = queue_url.rpartition('/')
    cancel_suffix = f'{queue_name}-cancels' if queue_name else 'dagster-cancels'
    return f'{prefix}/{cancel_suffix}' if prefix else cancel_suffix
