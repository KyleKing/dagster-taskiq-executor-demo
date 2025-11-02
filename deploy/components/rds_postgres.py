"""Reusable PostgreSQL database component."""

from collections.abc import Sequence
from dataclasses import dataclass

import pulumi
from pulumi_aws import Provider, rds


@dataclass
class DatabaseResources:
    """Outputs for the Dagster PostgreSQL instance."""

    subnet_group: rds.SubnetGroup
    instance: rds.Instance


def create_postgres_database(
    resource_name: str,
    *,
    provider: Provider,
    subnet_ids: Sequence[str],
    security_group_ids: Sequence[pulumi.Input[str]],
    db_name: str,
    username: str,
    password: str,
    instance_class: str,
    allocated_storage: int,
    max_allocated_storage: int,
    engine_version: str,
    project_name: str,
    environment: str,
) -> DatabaseResources:
    """Provision a PostgreSQL instance suitable for Dagster metadata storage.

    Returns:
        DatabaseResources: Wrapper containing the subnet group and RDS instance.
    """
    subnet_group = rds.SubnetGroup(
        f"{resource_name}-subnet-group",
        name=f"{project_name}-rds-{environment}",
        subnet_ids=list(subnet_ids),
        description="Subnet group for Dagster RDS instance",
        opts=pulumi.ResourceOptions(provider=provider),
    )

    instance = rds.Instance(
        # HACK: temporary settings for LocalStack, but will eventually migrate to best practices
        f"{resource_name}-instance",
        identifier=f"{project_name}-rds-{environment}",
        engine="postgres",
        engine_version=engine_version,
        instance_class=instance_class,
        allocated_storage=allocated_storage,
        max_allocated_storage=max_allocated_storage,
        storage_type="gp2",
        storage_encrypted=False,
        db_name=db_name,
        username=username,
        password=password,
        vpc_security_group_ids=security_group_ids,
        db_subnet_group_name=subnet_group.name,
        skip_final_snapshot=True,
        publicly_accessible=True,
        backup_retention_period=7,
        backup_window="03:00-04:00",
        maintenance_window="sun:04:00-sun:05:00",
        auto_minor_version_upgrade=True,
        multi_az=False,
        monitoring_interval=0,
        performance_insights_enabled=False,
        deletion_protection=False,
        parameter_group_name="default.postgres15",
        opts=pulumi.ResourceOptions(provider=provider),
        port=4510,  # Appears to be required for LocalStack?
        # https://www.pulumi.com/registry/packages/aws/api-docs/rds/instance/#port_nodejs
    )

    return DatabaseResources(subnet_group=subnet_group, instance=instance)
