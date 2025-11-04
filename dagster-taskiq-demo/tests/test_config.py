"""Tests for configuration modules."""

from __future__ import annotations

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


