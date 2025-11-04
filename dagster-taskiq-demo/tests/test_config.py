"""Tests for configuration modules."""

from __future__ import annotations

import pathlib
import tempfile
from unittest.mock import Mock, patch

import pytest
import yaml

from dagster_taskiq_demo.config.dagster import (
    DagsterPostgreSQLConfig,
    RetryablePostgresStorage,
    get_dagster_instance_config,
)
from dagster_taskiq_demo.config.exceptions import DagsterDatabaseConnectionError
from dagster_taskiq_demo.config.settings import Settings


def test_settings_from_env_test(test_settings: Settings) -> None:
    """Settings load correctly from .env.test."""
    # AWS settings from .env.test
    assert test_settings.aws_region == "us-east-1"
    assert test_settings.aws_endpoint_url == "http://localhost:4566"
    assert test_settings.aws_access_key_id == "test"
    assert test_settings.aws_secret_access_key == "test"

    # Database settings from .env.test
    assert test_settings.postgres_host == "localhost"
    assert test_settings.postgres_port == 5432
    assert test_settings.postgres_user == "test"
    assert test_settings.postgres_password == "test"
    assert test_settings.postgres_db == "test"

    # Dagster settings from .env.test
    assert test_settings.dagster_home == "/tmp/dagster_test"
    assert test_settings.dagster_webserver_host == "localhost"
    assert test_settings.dagster_webserver_port == 3001


def test_postgres_url_property(test_settings: Settings) -> None:
    """postgres_url property construction."""
    expected_url = "postgresql://test:test@localhost:5432/test"
    assert test_settings.postgres_url == expected_url


def test_dagster_postgres_url_property(test_settings: Settings) -> None:
    """dagster_postgres_url property construction."""
    expected_url = "postgresql+psycopg://test:test@localhost:5432/test"
    assert test_settings.dagster_postgres_url == expected_url


def test_get_postgres_storage_config(test_settings: Settings) -> None:
    """PostgreSQL storage configuration generation."""
    with patch("dagster_taskiq_demo.config.dagster.settings", test_settings):
        config = DagsterPostgreSQLConfig.get_postgres_storage_config()

    assert "postgres_url" in config
    assert config["postgres_url"] == test_settings.dagster_postgres_url
    assert config["should_autocreate_tables"] is True


def test_get_run_storage_config(test_settings: Settings) -> None:
    """Run storage configuration generation."""
    with patch("dagster_taskiq_demo.config.dagster.settings", test_settings):
        config = DagsterPostgreSQLConfig.get_run_storage_config()

    assert config["module"] == "dagster_postgres.run_storage"
    assert config["class"] == "DagsterPostgresRunStorage"
    assert "config" in config
    assert config["config"]["postgres_url"] == test_settings.dagster_postgres_url


def test_get_event_log_storage_config(test_settings: Settings) -> None:
    """Event log storage configuration generation."""
    with patch("dagster_taskiq_demo.config.dagster.settings", test_settings):
        config = DagsterPostgreSQLConfig.get_event_log_storage_config()

    assert config["module"] == "dagster_postgres.event_log"
    assert config["class"] == "DagsterPostgresEventLogStorage"
    assert "config" in config
    assert config["config"]["postgres_url"] == test_settings.dagster_postgres_url


def test_get_schedule_storage_config(test_settings: Settings) -> None:
    """Schedule storage configuration generation."""
    with patch("dagster_taskiq_demo.config.dagster.settings", test_settings):
        config = DagsterPostgreSQLConfig.get_schedule_storage_config()

    assert config["module"] == "dagster_postgres.schedule_storage"
    assert config["class"] == "DagsterPostgresScheduleStorage"
    assert "config" in config
    assert config["config"]["postgres_url"] == test_settings.dagster_postgres_url


def test_get_compute_log_storage_config() -> None:
    """Compute log storage configuration generation."""
    config = DagsterPostgreSQLConfig.get_compute_log_storage_config()

    assert config["module"] == "dagster._core.storage.noop_compute_log_manager"
    assert config["class"] == "NoOpComputeLogManager"


def test_get_dagster_yaml_config(test_settings: Settings) -> None:
    """Complete Dagster YAML configuration generation."""
    with patch("dagster_taskiq_demo.config.dagster.settings", test_settings):
        config = DagsterPostgreSQLConfig.get_dagster_yaml_config()

    # Check top-level structure
    assert "storage" in config
    assert "run_coordinator" in config
    assert "run_launcher" in config
    assert "compute_logs" in config

    # Check storage configuration
    storage = config["storage"]
    assert "postgres" in storage
    assert storage["postgres"]["postgres_url"] == test_settings.dagster_postgres_url
    assert storage["postgres"]["should_autocreate_tables"] is True

    # Check run coordinator
    assert config["run_coordinator"]["class"] == "DefaultRunCoordinator"

    # Check run launcher
    assert config["run_launcher"]["class"] == "DefaultRunLauncher"


def test_create_storage_success_first_try() -> None:
    """Successful storage creation on first attempt."""
    postgres_url = "postgresql://test:test@localhost:5432/test"
    storage = RetryablePostgresStorage(postgres_url, max_retries=3, retry_delay=0.1)

    with patch("dagster_taskiq_demo.config.dagster.DagsterPostgresStorage") as mock_storage_class:
        mock_instance = Mock()
        mock_storage_class.return_value = mock_instance

        result = storage.create_storage()

    assert result == mock_instance
    mock_storage_class.assert_called_once_with(
        postgres_url=postgres_url,
        should_autocreate_tables=True,
    )


def test_create_storage_success_after_retries() -> None:
    """Successful storage creation after retries."""
    postgres_url = "postgresql://test:test@localhost:5432/test"
    storage = RetryablePostgresStorage(postgres_url, max_retries=3, retry_delay=0.01)

    with patch("dagster_taskiq_demo.config.dagster.DagsterPostgresStorage") as mock_storage_class:
        mock_instance = Mock()
        # Fail twice, then succeed
        mock_storage_class.side_effect = [
            ConnectionError("Connection failed"),
            ConnectionError("Connection failed"),
            mock_instance,
        ]

        with patch("time.sleep") as mock_sleep:
            result = storage.create_storage()

    assert result == mock_instance
    assert mock_storage_class.call_count == 3
    assert mock_sleep.call_count == 2  # Sleep after first two failures


def test_create_storage_failure_after_max_retries() -> None:
    """Storage creation failure after max retries."""
    postgres_url = "postgresql://test:test@localhost:5432/test"
    storage = RetryablePostgresStorage(postgres_url, max_retries=2, retry_delay=0.01)

    with patch("dagster_taskiq_demo.config.dagster.DagsterPostgresStorage") as mock_storage_class:
        mock_storage_class.side_effect = ConnectionError("Connection failed")

        with patch("time.sleep"), pytest.raises(DagsterDatabaseConnectionError) as exc_info:
            storage.create_storage()

    assert "Failed to connect to PostgreSQL after 2 attempts" in str(exc_info.value)
    assert mock_storage_class.call_count == 2




def test_get_dagster_instance_config(test_settings: Settings) -> None:
    """Programmatic Dagster instance configuration."""
    with patch("dagster_taskiq_demo.config.dagster.settings", test_settings):
        config = get_dagster_instance_config()

    # Should have same structure as YAML config
    assert "storage" in config
    assert "run_coordinator" in config
    assert "run_launcher" in config
    assert "compute_logs" in config

    # Should use test settings
    assert config["storage"]["postgres"]["postgres_url"] == test_settings.dagster_postgres_url
