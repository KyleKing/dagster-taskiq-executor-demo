"""Pytest configuration and fixtures for dagster-taskiq tests."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Generator
from unittest.mock import Mock, patch

import pytest
from dagster import DagsterInstance, build_op_context, build_job_context
from dagster.core.test_utils import instance_for_test

from dagster_taskiq.config.settings import Settings


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with safe defaults."""
    return Settings(
        aws_region="us-east-1",
        aws_endpoint_url="http://localhost:4566",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        postgres_host="localhost",
        postgres_port=5432,
        postgres_user="test",
        postgres_password="test",
        postgres_db="test",
        taskiq_queue_name="test-queue.fifo",
        taskiq_dlq_name="test-dlq.fifo",
        ecs_cluster_name="test-cluster",
        dagster_home="/tmp/dagster_test",
        dagster_webserver_host="localhost",
        dagster_webserver_port=3001,
        taskiq_worker_concurrency=2,
        taskiq_visibility_timeout=60,
        autoscaler_min_workers=1,
        autoscaler_max_workers=5,
        autoscaler_scale_up_threshold=3,
        autoscaler_scale_down_threshold=1,
        autoscaler_cooldown_seconds=30,
        load_sim_job_interval_seconds=60,
        load_sim_fast_job_duration_base=5,
        load_sim_fast_job_duration_variance=2,
        load_sim_slow_job_duration_base=30,
        load_sim_slow_job_duration_variance=10,
        log_level="DEBUG",
    )


@pytest.fixture
def dagster_instance() -> Generator[DagsterInstance, None, None]:
    """Create a test Dagster instance."""
    with instance_for_test() as instance:
        yield instance


@pytest.fixture
def mock_op_context(dagster_instance: DagsterInstance) -> Mock:
    """Create a mock operation context for testing."""
    context = build_op_context(instance=dagster_instance)
    return context


@pytest.fixture
def mock_job_context(dagster_instance: DagsterInstance) -> Mock:
    """Create a mock job context for testing."""
    context = build_job_context(instance=dagster_instance)
    return context


@pytest.fixture(autouse=True)
def patch_settings(test_settings: Settings) -> Generator[None, None, None]:
    """Automatically patch settings for all tests."""
    with patch("dagster_taskiq.config.settings.settings", test_settings):
        yield


@pytest.fixture
def mock_asyncio_sleep() -> Generator[Mock, None, None]:
    """Mock asyncio.sleep to speed up tests."""
    with patch("asyncio.sleep", new_callable=Mock) as mock_sleep:
        mock_sleep.return_value = asyncio.Future()
        mock_sleep.return_value.set_result(None)
        yield mock_sleep


@pytest.fixture
def mock_secrets_randbelow() -> Generator[Mock, None, None]:
    """Mock secrets.randbelow for predictable test results."""
    with patch("secrets.randbelow", return_value=0) as mock_randbelow:
        yield mock_randbelow


@pytest.fixture
def mock_loop_time() -> Generator[Mock, None, None]:
    """Mock asyncio event loop time for predictable test results."""
    start_time = 1000.0
    with patch("asyncio.get_event_loop") as mock_get_loop:
        mock_loop = Mock()
        mock_loop.time.side_effect = [start_time, start_time + 20.0]  # 20 second duration
        mock_get_loop.return_value = mock_loop
        yield mock_loop.time