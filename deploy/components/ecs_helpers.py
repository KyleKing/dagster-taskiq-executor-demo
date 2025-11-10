"""Helper utilities for ECS task definitions and common patterns."""

from dataclasses import dataclass
from typing import Any

import pulumi
from pulumi_aws import Provider, ecs


@dataclass
class LogConfig:
    """CloudWatch Logs configuration."""

    log_group: str
    region: str
    stream_prefix: str = "ecs"


@dataclass
class HealthCheck:
    """Container health check configuration."""

    command: list[str]
    interval: int = 30
    timeout: int = 5
    retries: int = 3
    start_period: int = 60


@dataclass
class PortMapping:
    """Container port mapping."""

    container_port: int
    protocol: str = "tcp"
    name: str | None = None


@dataclass
class ContainerDefinition:
    """High-level container definition builder."""

    name: str
    image: str
    environment: dict[str, str]
    essential: bool = True
    command: list[str] | None = None
    port_mappings: list[PortMapping] | None = None
    health_check: HealthCheck | None = None
    log_config: LogConfig | None = None
    stop_timeout: int = 30

    def to_dict(self) -> dict[str, Any]:
        """Convert to AWS ECS container definition format.

        Returns:
            dict[str, Any]: Container definition in AWS ECS format
        """
        definition: dict[str, Any] = {
            "name": self.name,
            "image": self.image,
            "essential": self.essential,
            "environment": [{"name": k, "value": v} for k, v in self.environment.items()],
            "stopTimeout": self.stop_timeout,
        }

        if self.command:
            definition["command"] = self.command

        if self.port_mappings:
            definition["portMappings"] = [
                {
                    "containerPort": pm.container_port,
                    "protocol": pm.protocol,
                    **({"name": pm.name} if pm.name else {}),
                }
                for pm in self.port_mappings
            ]

        if self.health_check:
            definition["healthCheck"] = {
                "command": self.health_check.command,
                "interval": self.health_check.interval,
                "timeout": self.health_check.timeout,
                "retries": self.health_check.retries,
                "startPeriod": self.health_check.start_period,
            }

        if self.log_config:
            definition["logConfiguration"] = {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": self.log_config.log_group,
                    "awslogs-region": self.log_config.region,
                    "awslogs-stream-prefix": self.log_config.stream_prefix,
                    "awslogs-create-group": "true",
                },
            }

        return definition


def create_fargate_task_definition(
    resource_name: str,
    *,
    provider: Provider,
    family: str,
    container_definitions: pulumi.Input[str],
    execution_role_arn: pulumi.Input[str],
    task_role_arn: pulumi.Input[str],
    cpu: str = "512",
    memory: str = "1024",
) -> ecs.TaskDefinition:
    """Create a Fargate-compatible ECS task definition with common defaults.

    Args:
        resource_name: Pulumi resource name
        provider: AWS provider
        family: Task definition family name
        container_definitions: JSON string of container definitions
        execution_role_arn: ARN of the execution role
        task_role_arn: ARN of the task role
        cpu: CPU units (default: 512)
        memory: Memory in MiB (default: 1024)

    Returns:
        ecs.TaskDefinition: The created task definition
    """
    return ecs.TaskDefinition(
        resource_name,
        family=family,
        network_mode="awsvpc",
        requires_compatibilities=["FARGATE"],
        cpu=cpu,
        memory=memory,
        execution_role_arn=execution_role_arn,
        task_role_arn=task_role_arn,
        container_definitions=container_definitions,
        opts=pulumi.ResourceOptions(provider=provider),
    )
