"""FastAPI service exposing TaskIQ queue operations."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, status
from pydantic import BaseModel, Field
from structlog.stdlib import BoundLogger

from .config import Settings, get_settings
from .logging import configure_logging, get_logger
from .tasks import enqueue_sleep

app = FastAPI(
    title="TaskIQ Demo API",
    version="0.0.0",
)

_logger: BoundLogger | None = None


def _get_logger() -> BoundLogger:
    global _logger
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


@app.on_event("startup")
async def startup() -> None:
    """Configure logging before handling requests."""
    configure_logging()
    _get_logger().info("api.startup")


@app.get("/health")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    """Simple health endpoint for container orchestration."""
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
    """Accept a sleep duration and enqueue it for the TaskIQ worker."""
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
