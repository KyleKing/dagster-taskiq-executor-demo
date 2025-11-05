# Modifications copyright (c) 2024 dagster-taskiq contributors

"""Cancellable receiver for TaskIQ with task cancellation support."""

import asyncio
import logging
from contextlib import suppress
from typing import Any

import anyio
from taskiq.message import TaskiqMessage
from taskiq.receiver import Receiver

logger = logging.getLogger(__name__)

CANCELLER_KEY = "__cancel_task_id__"

# Sentinel object to indicate queue is done
_QUEUE_DONE = object()

logger.info("Loaded CancellableReceiver from %s", __file__)


class CancellableReceiver(Receiver):
    """Receiver that supports cancelling running tasks."""

    QUEUE_DONE = _QUEUE_DONE

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the cancellable receiver.

        Args:
            *args: Positional arguments passed to parent Receiver
            **kwargs: Keyword arguments passed to parent Receiver
        """
        super().__init__(*args, **kwargs)
        self.tasks: set[asyncio.Task[Any]] = set()

    def parse_message(self, message: bytes | Any) -> TaskiqMessage | None:
        """Parse a message into a TaskiqMessage.

        Args:
            message: Raw message bytes or message object

        Returns:
            Parsed TaskiqMessage or None if parsing fails
        """
        message_data = message.data if hasattr(message, "data") else message  # pyright: ignore[reportAttributeAccessIssue]
        try:
            taskiq_msg = self.broker.formatter.loads(message=message_data)
            taskiq_msg.parse_labels()
        except Exception as exc:
            logger.warning(
                "Cannot parse message: %s. Skipping execution.\n %s",
                message_data,
                exc,
                exc_info=True,
            )
            return None
        return taskiq_msg

    async def prefetcher(self, queue: asyncio.Queue[bytes | Any], finish_event: asyncio.Event) -> None:
        """Override prefetcher to ensure QUEUE_DONE is sent when finished."""
        try:
            await super().prefetcher(queue, finish_event)
        finally:
            # Ensure QUEUE_DONE is sent to signal completion
            with suppress(Exception):  # Queue might be closed, that's fine
                queue.put_nowait(self.QUEUE_DONE)

    async def listen(self, finish_event: asyncio.Event) -> None:
        """Listen for messages and cancellations concurrently."""
        if self.run_startup:
            await self.broker.startup()
        logger.info("Listening started.")

        queue: asyncio.Queue[bytes | Any] = asyncio.Queue()

        async with anyio.create_task_group() as gr:
            gr.start_soon(self.prefetcher, queue, finish_event)
            gr.start_soon(self.runner, queue)
            gr.start_soon(self.runner_canceller, finish_event)

        if self.on_exit is not None:
            self.on_exit(self)

    async def runner_canceller(self, finish_event: asyncio.Event) -> None:  # noqa: C901
        """Listen for cancellation messages and cancel tasks."""

        def cancel_task(task_id: str) -> None:
            for task in self.tasks:
                if task.get_name() == task_id:
                    if task.cancel():
                        logger.info("Cancelling task %s", task_id)
                    else:
                        logger.warning("Cannot cancel task %s", task_id)

        async for message in self.broker.listen_canceller():  # pyright: ignore[reportAttributeAccessIssue]  # type: ignore[attr-defined,method-assign]
            if finish_event.is_set():
                break
            try:
                taskiq_msg = self.parse_message(message)
                if not taskiq_msg:
                    continue

                if CANCELLER_KEY in taskiq_msg.kwargs:
                    cancel_task(taskiq_msg.kwargs[CANCELLER_KEY])
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in canceller")

    async def runner(self, queue: asyncio.Queue[bytes | Any]) -> None:
        """Run tasks from the queue."""

        def task_cb(task: asyncio.Task[Any]) -> None:
            self.tasks.discard(task)
            if self.sem is not None:
                self.sem.release()

        while True:
            if self.sem is not None:
                await self.sem.acquire()

            self.sem_prefetch.release()
            message = await queue.get()
            if message is self.QUEUE_DONE:
                break

            taskiq_msg = self.parse_message(message)
            if not taskiq_msg:
                continue

            task = asyncio.create_task(
                self.callback(message=message, raise_err=False),
                name=str(taskiq_msg.task_id),
            )
            self.tasks.add(task)
            task.add_done_callback(task_cb)
