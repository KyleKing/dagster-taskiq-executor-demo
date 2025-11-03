"""Tests for config.py StackSettings loader."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from config import StackSettings


def test_load_with_full_config(mock_pulumi_config: MagicMock) -> None:
    """Arrange: Mock Pulumi config with all values provided."""
    with patch("pulumi.Config", return_value=mock_pulumi_config):
        # Act: Load stack settings
        settings = StackSettings.load()

        # Assert: All settings are loaded correctly
        assert isinstance(settings, StackSettings)
        assert settings.project.name == "dagster-taskiq-demo"
        assert settings.project.environment == "test"
        assert settings.aws.region == "us-east-1"
        assert settings.aws.endpoint == "http://localhost:4566"
        assert settings.aws.access_key == "test"
        assert settings.aws.secret_key == "test"
        assert settings.queue.message_retention_seconds == 1209600
        assert settings.queue.visibility_timeout == 900
        assert settings.queue.dlq_visibility_timeout == 300
        assert settings.queue.redrive_max_receive_count == 3
        assert settings.database.engine_version == "17"
        assert settings.database.min_capacity == 0.5
        assert settings.database.max_capacity == 1.0
        assert settings.database.username == "dagster"
        assert settings.database.password == "dagster"
        assert settings.database.db_name == "dagster"
        assert settings.database.backup_retention_period == 7
        assert settings.database.deletion_protection is True  # From conftest fixture
        assert settings.database.publicly_accessible is True
        assert settings.services.daemon_desired_count == 1
        assert settings.services.webserver_desired_count == 1
        assert settings.services.worker_desired_count == 2
        assert settings.taskiq_demo.enabled is True
        assert settings.taskiq_demo.queue_name == "taskiq-demo"
        assert settings.taskiq_demo.message_retention_seconds == 604800
        assert settings.taskiq_demo.visibility_timeout == 120
        assert settings.taskiq_demo.api_desired_count == 1
        assert settings.taskiq_demo.worker_desired_count == 1
        assert settings.taskiq_demo.image_tag == "taskiq-demo"
        assert settings.taskiq_demo.assign_public_ip is True


@patch("pulumi.get_stack")
def test_load_with_defaults(mock_get_stack: MagicMock) -> None:
    """Arrange: Mock Pulumi config with minimal values."""
    mock_get_stack.return_value = "local"

    config = MagicMock()

    def mock_get_object(key: str) -> Mapping[str, Any] | None:
        if key == "project":
            return {}
        return {}

    config.get_object = mock_get_object

    with patch("pulumi.Config", return_value=config):
        # Act: Load stack settings
        settings = StackSettings.load()

        # Assert: Default values are applied
        assert settings.project.name == "dagster-taskiq-demo"
        assert settings.project.environment == "local"
        assert settings.aws.region == "us-east-1"
        assert settings.aws.endpoint == "http://localhost:4566"
        assert settings.queue.message_retention_seconds == 14 * 24 * 60 * 60  # 14 days
        assert settings.queue.visibility_timeout == 15 * 60  # 15 minutes
        assert settings.queue.dlq_visibility_timeout == 60
        assert settings.queue.redrive_max_receive_count == 3
        assert settings.database.engine_version == "17"
        assert settings.database.min_capacity == 0.5
        assert settings.database.max_capacity == 1.0
        assert settings.database.username == "dagster"
        assert settings.database.password == "dagster"
        assert settings.database.db_name == "dagster"
        assert settings.database.backup_retention_period == 7
        assert settings.database.deletion_protection is False
        assert settings.database.publicly_accessible is True
        assert settings.services.daemon_desired_count == 1
        assert settings.services.webserver_desired_count == 1
        assert settings.services.worker_desired_count == 2
        assert settings.taskiq_demo.enabled is False
        assert settings.taskiq_demo.queue_name == "taskiq-demo"
        assert settings.taskiq_demo.message_retention_seconds == 7 * 24 * 60 * 60
        assert settings.taskiq_demo.visibility_timeout == 120
        assert settings.taskiq_demo.api_desired_count == 1
        assert settings.taskiq_demo.worker_desired_count == 1
        assert settings.taskiq_demo.image_tag == "taskiq-demo"
        assert settings.taskiq_demo.assign_public_ip is True


def test_load_with_invalid_config_type() -> None:
    """Arrange: Mock Pulumi config returning invalid type."""
    config = MagicMock()

    def mock_get_object(key: str) -> Mapping[str, Any] | None:
        if key == "project":
            return "invalid_string"  # type: ignore[return-value]  # Should be a mapping
        return {}

    config.get_object = mock_get_object

    # Act & Assert: Should raise TypeError
    with (
        patch("pulumi.Config", return_value=config),
        pytest.raises(
            TypeError,
            match=r"Pulumi config key 'project' must be an object.",
        ),
    ):
        StackSettings.load()


def test_load_with_missing_config_sections() -> None:
    """Arrange: Mock Pulumi config returning None for missing sections."""
    config = MagicMock()

    def mock_get_object(key: str) -> Mapping[str, Any] | None:
        return None  # All sections missing

    config.get_object = mock_get_object

    with patch("pulumi.Config", return_value=config), patch("pulumi.get_stack", return_value="local"):
        # Act: Load stack settings
        settings = StackSettings.load()

        # Assert: Should use defaults for all missing sections
        assert isinstance(settings, StackSettings)
        assert settings.project.name == "dagster-taskiq-demo"
        assert settings.project.environment == "local"  # Default from get_stack()
        assert settings.taskiq_demo.enabled is False


@pytest.mark.parametrize(
    ("config_key", "field_name", "expected_value"),
    [
        ("project", "name", "custom-project"),
        ("aws", "region", "eu-west-1"),
        ("queue", "messageRetentionSeconds", "864000"),
        ("database", "engineVersion", "16"),
        ("services", "daemonDesiredCount", "3"),
        ("taskiqDemo", "queueName", "custom-queue"),
    ],
)
def test_load_individual_config_overrides(config_key: str, field_name: str, expected_value: str) -> None:
    """Arrange: Mock Pulumi config with specific overrides."""
    config = MagicMock()

    def mock_get_object(key: str) -> Mapping[str, Any] | None:
        if key == config_key:
            return {field_name: expected_value}
        return {}

    config.get_object = mock_get_object

    with patch("pulumi.Config", return_value=config):
        # Act: Load stack settings
        settings = StackSettings.load()

        # Assert: Specific field is overridden
        if config_key == "project":
            assert getattr(settings.project, field_name) == expected_value
        elif config_key == "aws":
            assert getattr(settings.aws, field_name) == expected_value
        elif config_key == "queue":
            if field_name == "messageRetentionSeconds":
                assert settings.queue.message_retention_seconds == int(expected_value)
        elif config_key == "database":
            if field_name == "engineVersion":
                assert settings.database.engine_version == expected_value
        elif config_key == "services" and field_name == "daemonDesiredCount":
            assert settings.services.daemon_desired_count == int(expected_value)
        elif config_key == "taskiqDemo" and field_name == "queueName":
            assert settings.taskiq_demo.queue_name == expected_value
