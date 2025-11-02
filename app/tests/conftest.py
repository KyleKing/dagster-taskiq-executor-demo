"""Pytest configuration and fixtures for dagster-taskiq tests."""

from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest
from dagster import DagsterInstance
from dagster.core.test_utils import instance_for_test

from dagster_taskiq.config.settings import Settings


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings from .env.test file.

    Uses pydantic-settings to load configuration from .env.test,
    avoiding complex environment variable mocking.
    """
    return Settings(_env_file=".env.test", _env_file_encoding="utf-8")


@pytest.fixture
def dagster_instance() -> Generator[DagsterInstance]:
    """Create a test Dagster instance."""
    with instance_for_test() as instance:
        yield instance


# Simple mocks for speeding up integration tests without mocking Dagster internals


@pytest.fixture
def mock_asyncio_sleep(monkeypatch):
    """Mock asyncio.sleep to make tests run instantly.

    This is a simple mock that doesn't touch Dagster internals - it just
    makes asyncio.sleep return immediately for faster test execution.
    """

    async def instant_sleep(_duration):
        """Instantly return without sleeping."""
        pass

    monkeypatch.setattr("asyncio.sleep", instant_sleep)


@pytest.fixture
def mock_secrets_randbelow(monkeypatch):
    """Mock secrets.randbelow to return deterministic values.

    Returns 0 to give minimal variance (negative of the variance value)
    for predictable test results without mocking Dagster internals.
    """
    monkeypatch.setattr("secrets.randbelow", lambda _x: 0)






