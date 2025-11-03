"""TaskIQ task definitions and broker wiring."""

from __future__ import annotations

import asyncio
from typing import Any

from taskiq_aio_sqs import SQSBroker

from .config import get_settings
from .logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level_value)
logger = get_logger(__name__)

broker = SQSBroker(
    endpoint_url=str(settings.sqs_endpoint_url),
    sqs_queue_name=settings.sqs_queue_name,
    region_name=settings.aws_region,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    wait_time_seconds=settings.wait_time_seconds,
    max_number_of_messages=1,
    delay_seconds=settings.message_delay_seconds,
)

taskiq_app = broker


async def perform_sleep(duration_seconds: float) -> dict[str, Any]:
    """Execute the sleep payload with clamped duration.

    Args:
        duration_seconds: The duration to sleep.

    Returns:
        The result dictionary with duration.

    """
    duration = settings.clamp_duration(duration_seconds)
    logger.info(
        "task.start",
        requested_duration=duration_seconds,
        duration_seconds=duration,
    )
    await asyncio.sleep(duration)
    logger.info("task.complete", duration_seconds=duration)
    return {"duration_seconds": duration}


@broker.task()
async def sleep_task(duration_seconds: float) -> dict[str, Any]:
    """TaskIQ entrypoint for sleeping.

    Args:
        duration_seconds: The duration to sleep.

    Returns:
        The result dictionary with duration.

    """
    return await perform_sleep(duration_seconds)


async def enqueue_sleep(duration_seconds: float) -> Any:
    """Enqueue a sleep task.

    Args:
        duration_seconds: The duration to sleep.

    Returns:
        The task result.

    """
    return await sleep_task.kiq(duration_seconds=duration_seconds)
