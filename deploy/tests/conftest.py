"""Test configuration and fixtures for Pulumi infrastructure testing."""

from __future__ import annotations

from collections.abc import Mapping
from unittest.mock import AsyncMock, MagicMock

import pulumi
import pulumi_aws
import pytest

from config import (
    AwsSettings,
    DatabaseSettings,
    ProjectSettings,
    QueueSettings,
    ServiceSettings,
    StackSettings,
)


@pytest.fixture
def mock_pulumi_config() -> MagicMock:
    """Mock Pulumi configuration for testing.

    Returns:
        MagicMock: Pulumi configuration stub with predefined values.
    """
    config = MagicMock(spec=pulumi.Config)

    def mock_get_object(key: str) -> Mapping[str, str] | None:
        config_map = {
            "project": {
                "name": "dagster-taskiq-demo",
                "environment": "test",
            },
            "aws": {
                "region": "us-east-1",
                "endpoint": "http://localhost:4566",
                "accessKey": "test",
                "secretKey": "test",
            },
            "queue": {
                "messageRetentionSeconds": "1209600",
                "visibilityTimeout": "900",
                "dlqVisibilityTimeout": "300",
                "redriveMaxReceiveCount": "3",
            },
            "database": {
                "engineVersion": "17",
                "minCapacity": "0.5",
                "maxCapacity": "1.0",
                "username": "dagster",
                "password": "dagster",
                "dbName": "dagster",
                "backupRetentionPeriod": "7",
                "deletionProtection": "false",
                "publiclyAccessible": "true",
            },
            "services": {
                "daemonDesiredCount": "1",
                "webserverDesiredCount": "1",
                "workerDesiredCount": "2",
            },
        }
        return config_map.get(key)

    config.get_object = mock_get_object
    return config


@pytest.fixture
def mock_aws_provider() -> MagicMock:
    """Mock AWS provider for testing.

    Returns:
        MagicMock: Provider mock with minimal Pulumi attributes.
    """
    provider = MagicMock(spec=pulumi_aws.Provider)
    provider.package = "aws"

    # Mock the urn property to be awaitable
    mock_urn = AsyncMock()
    mock_urn.future.return_value = AsyncMock()
    provider.urn = mock_urn

    # Mock the id property to be awaitable
    mock_id = AsyncMock()
    mock_id.future.return_value = AsyncMock()
    provider.id = mock_id

    return provider


@pytest.fixture
def sample_stack_settings() -> StackSettings:
    """Sample StackSettings for testing.

    Returns:
        StackSettings: Representative stack configuration.
    """
    return StackSettings(
        project=ProjectSettings(name="dagster-taskiq-demo", environment="test"),
        aws=AwsSettings(
            region="us-east-1",
            endpoint="http://localhost:4566",
            access_key="test",
            secret_key="test",
        ),
        queue=QueueSettings(
            message_retention_seconds=1209600,
            visibility_timeout=900,
            dlq_visibility_timeout=300,
            redrive_max_receive_count=3,
        ),
        database=DatabaseSettings(
            engine_version="17",
            min_capacity=0.5,
            max_capacity=1.0,
            username="dagster",
            password="dagster",
            db_name="dagster",
            backup_retention_period=7,
            deletion_protection=False,
            publicly_accessible=True,
        ),
        services=ServiceSettings(
            daemon_desired_count=1,
            webserver_desired_count=1,
            worker_desired_count=2,
        ),
    )


@pytest.fixture
def pulumi_mock_stack() -> str:
    """Mock Pulumi stack name.

    Returns:
        str: Stub stack identifier.
    """
    return "test"


@pytest.fixture
def sample_resource_args() -> dict[str, str | list[str]]:
    """Sample arguments for resource creation functions.

    Returns:
        dict[str, str | list[str]]: Minimal arguments for Dagster resources.
    """
    return {
        "resource_name": "test-resource",
        "project_name": "dagster-taskiq-demo",
        "environment": "test",
        "region": "us-east-1",
        "vpc_id": "vpc-12345678",
        "subnet_ids": ["subnet-12345678", "subnet-87654321"],
        "container_image": "dagster-taskiq-demo:latest",
        "aws_endpoint_url": "http://localhost:4566",
        "database_endpoint": "test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
        "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/dagster-taskiq-test.fifo",
        "cluster_name": "test-cluster",
        "execution_role_arn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
    }
