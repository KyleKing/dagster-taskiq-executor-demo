"""CloudWatch Logs utilities for ECS services."""

from __future__ import annotations

import pulumi
from pulumi_aws import Provider
from pulumi_aws.cloudwatch import LogGroup


def create_ecs_log_group(
    resource_name: str,
    *,
    provider: Provider,
    log_group_name: str,
    retention_in_days: int = 14,
) -> LogGroup:
    """Create a CloudWatch Log Group for ECS services.

    Args:
        resource_name: Pulumi resource name
        provider: AWS provider
        log_group_name: Name of the log group
        retention_in_days: Log retention period in days (default: 14)

    Returns:
        logs.LogGroup: The created log group
    """
    return LogGroup(
        resource_name,
        name=log_group_name,
        retention_in_days=retention_in_days,
        opts=pulumi.ResourceOptions(provider=provider),
    )
