"""Reusable Aurora PostgreSQL Serverless v2 database component."""

from collections.abc import Sequence
from dataclasses import dataclass

import pulumi
from pulumi_aws import Provider, kms, rds


@dataclass
class DatabaseResources:
    """Outputs for the Aurora PostgreSQL Serverless cluster."""

    kms_key: kms.Key
    subnet_group: rds.SubnetGroup
    cluster: rds.Cluster
    cluster_instance: rds.ClusterInstance


def create_postgres_database(
    resource_name: str,
    *,
    provider: Provider,
    subnet_ids: Sequence[str],
    security_group_ids: Sequence[pulumi.Input[str]],
    db_name: str,
    username: str,
    password: str,
    project_name: str,
    environment: str,
    engine_version: str = "17",
    min_capacity: float = 0.5,
    max_capacity: float = 1.0,
    publicly_accessible: bool = False,
    deletion_protection: bool = True,
    backup_retention_period: int = 7,
    enable_performance_insights: bool = True,
    performance_insights_retention_period: int = 7,
) -> DatabaseResources:
    """Provision an Aurora PostgreSQL Serverless v2 cluster with encryption and best practices.

    Args:
        resource_name: Base name for resources
        provider: AWS provider
        subnet_ids: VPC subnet IDs for the database
        security_group_ids: Security group IDs to attach
        db_name: Initial database name
        username: Master username
        password: Master password
        project_name: Project name for tagging
        environment: Environment name (dev, staging, prod)
        engine_version: Aurora PostgreSQL version (default: "17"). Note: Check AWS documentation
            for Aurora PostgreSQL version availability in your region
        min_capacity: Minimum Aurora Serverless v2 capacity units (0.5-128)
        max_capacity: Maximum Aurora Serverless v2 capacity units (0.5-128)
        publicly_accessible: Whether cluster is publicly accessible
        deletion_protection: Enable deletion protection
        backup_retention_period: Days to retain automated backups (1-35)
        enable_performance_insights: Enable Performance Insights
        performance_insights_retention_period: Days to retain Performance Insights data (7 or 731)

    Returns:
        DatabaseResources: Wrapper containing KMS key, subnet group, cluster, and instance.
    """
    # Create KMS key for encryption at rest
    kms_key = kms.Key(
        f"{resource_name}-kms-key",
        description=f"KMS key for {project_name} Aurora cluster encryption in {environment}",
        deletion_window_in_days=10,
        enable_key_rotation=True,
        tags={
            "Name": f"{project_name}-aurora-{environment}",
            "Project": project_name,
            "Environment": environment,
            "ManagedBy": "Pulumi",
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Create KMS key alias for easier identification
    kms.Alias(
        f"{resource_name}-kms-alias",
        name=f"alias/{project_name}-aurora-{environment}",
        target_key_id=kms_key.id,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Create DB subnet group
    subnet_group = rds.SubnetGroup(
        f"{resource_name}-subnet-group",
        name=f"{project_name}-aurora-{environment}",
        subnet_ids=list(subnet_ids),
        description=f"Subnet group for {project_name} Aurora cluster in {environment}",
        tags={
            "Name": f"{project_name}-aurora-{environment}",
            "Project": project_name,
            "Environment": environment,
            "ManagedBy": "Pulumi",
        },
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Create Aurora PostgreSQL Serverless v2 cluster
    cluster = rds.Cluster(
        f"{resource_name}-cluster",
        cluster_identifier=f"{project_name}-aurora-{environment}",
        engine="aurora-postgresql",
        engine_mode="provisioned",  # Required for Serverless v2
        engine_version=engine_version,
        database_name=db_name,
        master_username=username,
        master_password=password,
        db_subnet_group_name=subnet_group.name,
        vpc_security_group_ids=security_group_ids,
        # Encryption configuration
        storage_encrypted=True,
        kms_key_id=kms_key.arn,
        # Backup configuration
        backup_retention_period=backup_retention_period,
        preferred_backup_window="03:00-04:00",
        preferred_maintenance_window="sun:04:00-sun:05:00",
        # Serverless v2 scaling configuration
        serverlessv2_scaling_configuration=rds.ClusterServerlessv2ScalingConfigurationArgs(
            min_capacity=min_capacity,
            max_capacity=max_capacity,
        ),
        # Security and availability
        deletion_protection=deletion_protection,
        skip_final_snapshot=not deletion_protection,  # Skip snapshot only if deletion protection is off
        final_snapshot_identifier=(
            f"{project_name}-aurora-{environment}-final-snapshot" if deletion_protection else None
        ),
        # Performance and monitoring
        enabled_cloudwatch_logs_exports=["postgresql"],
        enable_http_endpoint=False,  # Data API not needed for Dagster
        # IAM and authentication
        iam_database_authentication_enabled=True,
        # Network
        port=5432,  # Standard PostgreSQL port
        # Auto minor version upgrades
        apply_immediately=False,  # Apply changes during maintenance window
        allow_major_version_upgrade=False,
        tags={
            "Name": f"{project_name}-aurora-{environment}",
            "Project": project_name,
            "Environment": environment,
            "ManagedBy": "Pulumi",
            "Engine": "aurora-postgresql",
        },
        opts=pulumi.ResourceOptions(
            provider=provider,
            depends_on=[kms_key, subnet_group],
        ),
    )

    # Create Aurora Serverless v2 instance
    cluster_instance = rds.ClusterInstance(
        f"{resource_name}-instance",
        identifier=f"{project_name}-aurora-{environment}-instance-1",
        cluster_identifier=cluster.id,
        instance_class="db.serverless",  # Required for Serverless v2
        engine="aurora-postgresql",
        engine_version=engine_version,
        publicly_accessible=publicly_accessible,
        # Performance Insights
        performance_insights_enabled=enable_performance_insights,
        performance_insights_kms_key_id=kms_key.arn if enable_performance_insights else None,
        performance_insights_retention_period=(
            performance_insights_retention_period if enable_performance_insights else None
        ),
        # Monitoring
        monitoring_interval=60 if enable_performance_insights else 0,
        # Auto minor version upgrades
        auto_minor_version_upgrade=True,
        apply_immediately=False,
        tags={
            "Name": f"{project_name}-aurora-{environment}-instance-1",
            "Project": project_name,
            "Environment": environment,
            "ManagedBy": "Pulumi",
        },
        opts=pulumi.ResourceOptions(
            provider=provider,
            depends_on=[cluster],
        ),
    )

    return DatabaseResources(
        kms_key=kms_key,
        subnet_group=subnet_group,
        cluster=cluster,
        cluster_instance=cluster_instance,
    )
