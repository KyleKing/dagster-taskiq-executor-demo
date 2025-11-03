"""FastAPI service exposing TaskIQ queue operations."""

from __future__ import annotations

from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated

import taskiq_fastapi
from fastapi import Depends, FastAPI, status
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger

from .config import Settings, get_settings
from .logging import configure_logging, get_logger
from .tasks import broker, enqueue_sleep

_logger: BoundLogger | None = None


def _get_logger() -> BoundLogger:
    global _logger  # noqa: PLW0603
    if _logger is None:
        configure_logging()
        _logger = get_logger(__name__)
    return _logger


class EnqueueRequest(BaseModel):
    """Request payload for enqueuing a sleep task."""

    duration_seconds: float = Field(
        ...,
        description="Requested sleep duration in seconds.",
        gt=0,
        lt=3600,
    )


class EnqueueResponse(BaseModel):
    """Response payload after enqueuing a task."""

    task_id: str
    duration_seconds: float
    queue: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: ARG001
    """Configure logging before handling requests."""
    configure_logging()
    logger = _get_logger()
    logger.info("api.startup")

    # Start the TaskIQ broker if not in worker process
    if not broker.is_worker_process:
        await broker.startup()
        logger.info("broker.started")

    yield

    # Shutdown the broker if not in worker process
    if not broker.is_worker_process:
        await broker.shutdown()
        logger.info("broker.shutdown")


app = FastAPI(
    title="TaskIQ Demo API",
    version="0.0.0",
    lifespan=lifespan,
)

# Initialize TaskIQ FastAPI integration
taskiq_fastapi.init(broker, "taskiq_demo.service:app")


@app.get("/health")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    """Provide a simple health endpoint for container orchestration.

    Args:
        settings: Application settings.

    Returns:
        Health status information.

    """
    return {"status": "ok", "queue": settings.sqs_queue_name}


@app.post(
    "/tasks",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EnqueueResponse,
)
async def enqueue_task(
    payload: EnqueueRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> EnqueueResponse:
    """Accept a sleep duration and enqueue it for the TaskIQ worker.

    Args:
        payload: The request payload with duration.
        settings: Application settings.

    Returns:
        The enqueue response with task details.

    """
    duration = settings.clamp_duration(payload.duration_seconds)
    result = await enqueue_sleep(duration_seconds=duration)
    task_id = result.task_id or ""
    _get_logger().info(
        "api.enqueue",
        requested_duration=payload.duration_seconds,
        task_id=task_id,
        duration_seconds=duration,
        queue=settings.sqs_queue_name,
    )
    return EnqueueResponse(
        task_id=task_id,
        duration_seconds=duration,
        queue=settings.sqs_queue_name,
    )
