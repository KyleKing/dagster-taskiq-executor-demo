# Modifications copyright (c) 2024 dagster-taskiq contributors

"""Cancellable receiver for TaskIQ with task cancellation support."""

import asyncio
import logging
from typing import Any

import anyio

from taskiq.abc.receiver import Receiver
from taskiq.message import TaskiqMessage

logger = logging.getLogger(__name__)

CANCELLER_KEY = "__cancel_task_id__"


class CancellableReceiver(Receiver):
    """Receiver that supports cancelling running tasks."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.tasks: set[asyncio.Task[Any]] = set()

    def parse_message(self, message: bytes | Any) -> TaskiqMessage | None:
        """Parse a message into a TaskiqMessage."""
        message_data = message.data if hasattr(message, 'data') else message
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

    async def listen(self) -> None:
        """Listen for messages and cancellations concurrently."""
        if self.run_startup:
            await self.broker.startup()
        logger.info("Listening started.")

        queue: asyncio.Queue[bytes | Any] = asyncio.Queue()

        async with anyio.create_task_group() as gr:
            gr.start_soon(self.prefetcher, queue)
            gr.start_soon(self.runner, queue)
            gr.start_soon(self.runner_canceller)

        if self.on_exit is not None:
            self.on_exit(self)

    async def runner_canceller(self) -> None:
        """Listen for cancellation messages and cancel tasks."""
        def cancel_task(task_id: str) -> None:
            for task in self.tasks:
                if task.get_name() == task_id:
                    if task.cancel():
                        logger.info("Cancelling task %s", task_id)
                    else:
                        logger.warning("Cannot cancel task %s", task_id)

        async for message in self.broker.listen_canceller():
            try:
                taskiq_msg = self.parse_message(message)
                if not taskiq_msg:
                    continue

                if CANCELLER_KEY in taskiq_msg.kwargs:
                    cancel_task(taskiq_msg.kwargs[CANCELLER_KEY])
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Error in canceller: %s", exc)

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
