"""Tests for TaskIQ tasks."""

import asyncio
from typing import Any

import pytest

from taskiq_demo import tasks
from taskiq_demo.config import get_settings


@pytest.mark.asyncio
async def test_perform_sleep_clamps_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that perform_sleep clamps duration and logs correctly."""
    settings = get_settings()
    calls: list[dict[str, Any]] = []

    async def _fake_sleep(duration: float) -> None:  # noqa: RUF029
        calls.append({"duration": duration})

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    result = await tasks.perform_sleep(duration_seconds=settings.min_duration_seconds / 2)

    assert calls == [{"duration": settings.min_duration_seconds}]
    assert result == {"duration_seconds": settings.min_duration_seconds}
