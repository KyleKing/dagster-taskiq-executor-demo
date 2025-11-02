"""Structured configuration loading for the Pulumi stack."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pulumi


@dataclass
class ProjectSettings:
    """High-level project metadata."""

    name: str
    environment: str


@dataclass
class AwsSettings:
    """Configuration for the LocalStack AWS provider."""

    region: str
    endpoint: str
    access_key: str
    secret_key: str


@dataclass
class QueueSettings:
    """Settings applied to the TaskIQ FIFO queue."""

    message_retention_seconds: int
    visibility_timeout: int
    dlq_visibility_timeout: int
    redrive_max_receive_count: int


@dataclass
class DatabaseSettings:
    """PostgreSQL configuration for Dagster metadata storage."""

    engine_version: str
    instance_class: str
    allocated_storage: int
    max_allocated_storage: int
    username: str
    password: str
    db_name: str


@dataclass
class ServiceSettings:
    """ECS service sizing configuration."""

    daemon_desired_count: int
    webserver_desired_count: int
    worker_desired_count: int


@dataclass
class StackSettings:
    """Aggregated configuration for the stack."""

    project: ProjectSettings
    aws: AwsSettings
    queue: QueueSettings
    database: DatabaseSettings
    services: ServiceSettings

    @classmethod
    def load(cls) -> StackSettings:
        """Load strongly typed stack settings from Pulumi configuration.

        Returns:
            StackSettings: Aggregated configuration for the active stack.
        """
        config = pulumi.Config()

        def _get_mapping(key: str) -> Mapping[str, Any]:
            value = config.get_object(key)
            if value is None:
                return {}
            if not isinstance(value, Mapping):
                msg = f"Pulumi config key '{key}' must be an object."
                raise TypeError(msg)
            return value

        project_cfg = _get_mapping("project")
        project = ProjectSettings(
            name=str(project_cfg.get("name", "dagster-taskiq-demo")),
            environment=str(project_cfg.get("environment", pulumi.get_stack())),
        )

        aws_cfg = _get_mapping("aws")
        aws = AwsSettings(
            region=str(aws_cfg.get("region", "us-east-1")),
            endpoint=str(aws_cfg.get("endpoint", "http://localhost:4566")),
            access_key=str(aws_cfg.get("accessKey", "test")),
            secret_key=str(aws_cfg.get("secretKey", "test")),
        )

        queue_cfg = _get_mapping("queue")
        queue = QueueSettings(
            message_retention_seconds=int(queue_cfg.get("messageRetentionSeconds", 14 * 24 * 60 * 60)),
            visibility_timeout=int(queue_cfg.get("visibilityTimeout", 15 * 60)),
            dlq_visibility_timeout=int(queue_cfg.get("dlqVisibilityTimeout", 60)),
            redrive_max_receive_count=int(queue_cfg.get("redriveMaxReceiveCount", 3)),
        )

        database_cfg = _get_mapping("database")
        database = DatabaseSettings(
            engine_version=str(database_cfg.get("engineVersion", "17.4")),
            instance_class=str(database_cfg.get("instanceClass", "db.t3.micro")),
            allocated_storage=int(database_cfg.get("allocatedStorage", 20)),
            max_allocated_storage=int(database_cfg.get("maxAllocatedStorage", 100)),
            username=str(database_cfg.get("username", "dagster")),
            password=str(database_cfg.get("password", "dagster")),
            db_name=str(database_cfg.get("dbName", "dagster")),
        )

        services_cfg = _get_mapping("services")
        services = ServiceSettings(
            daemon_desired_count=int(services_cfg.get("daemonDesiredCount", 1)),
            webserver_desired_count=int(services_cfg.get("webserverDesiredCount", 1)),
            worker_desired_count=int(services_cfg.get("workerDesiredCount", 2)),
        )

        return cls(
            project=project,
            aws=aws,
            queue=queue,
            database=database,
            services=services,
        )
