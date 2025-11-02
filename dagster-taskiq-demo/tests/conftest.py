"""Pytest configuration and fixtures for dagster-taskiq-demo tests."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Generator
from pathlib import Path

import pytest
from dagster import DagsterInstance
from dagster.core.test_utils import instance_for_test  # type: ignore[import-not-found]

from dagster_taskiq_demo.config.settings import Settings

# Configure pytest-postgresql to use mise-installed system Postgres
os.environ.setdefault("POSTGRESQL_HOST", "localhost")
os.environ.setdefault("POSTGRESQL_PORT", "5432")
os.environ.setdefault("POSTGRESQL_USER", "postgres")
os.environ.setdefault("POSTGRESQL_PASSWORD", "")
os.environ.setdefault("POSTGRESQL_DBNAME", "postgres")
os.environ.setdefault("POSTGRESQL_CONNECTION_TYPE", "psycopg")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    env_path = Path(__file__).resolve().parent.parent / ".env.test"
    env_vars: dict[str, str] = {}

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        env_vars[key] = value

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return Settings()


@pytest.fixture
def dagster_instance() -> Generator[DagsterInstance]:
    with instance_for_test() as instance:
        yield instance
