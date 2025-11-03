"""Tests for the FastAPI service endpoints."""

import dataclasses
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from taskiq_demo.config import get_settings
from taskiq_demo.service import app

STATUS_ACCEPTED = 202
STATUS_OK = 200


@dataclasses.dataclass
class _FakeResult:
    task_id: str


@pytest.mark.asyncio
async def test_enqueue_task_clamps_and_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that enqueueing a task clamps duration and dispatches correctly."""
    settings = get_settings()
    captures: dict[str, Any] = {}

    async def _fake_enqueue(duration_seconds: float) -> _FakeResult:  # noqa: RUF029
        captures["duration"] = duration_seconds
        return _FakeResult(task_id="task-123")

    monkeypatch.setattr("taskiq_demo.service.enqueue_sleep", _fake_enqueue)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/tasks", json={"duration_seconds": settings.max_duration_seconds * 2})

    assert response.status_code == STATUS_ACCEPTED
    data = response.json()
    assert data["task_id"] == "task-123"
    assert data["queue"] == settings.sqs_queue_name
    assert data["duration_seconds"] == pytest.approx(settings.max_duration_seconds)
    assert captures["duration"] == pytest.approx(settings.max_duration_seconds)


@pytest.mark.asyncio
async def test_health_endpoint_reports_queue() -> None:
    """Test that the health endpoint reports the correct queue name."""
    settings = get_settings()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == STATUS_OK
    assert response.json() == {"status": "ok", "queue": settings.sqs_queue_name}
