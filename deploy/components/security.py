"""Security group definitions for Dagster services."""

from collections.abc import Sequence
from dataclasses import dataclass

import pulumi
from pulumi_aws import Provider, ec2


@dataclass
class SecurityGroupResources:
    """Outputs for the Dagster shared security group."""

    security_group: ec2.SecurityGroup
    ingress_rules: Sequence[ec2.SecurityGroupRule]
    egress_rules: Sequence[ec2.SecurityGroupRule]


def create_dagster_security_group(
    resource_name: str,
    *,
    provider: Provider,
    vpc_id: str,
    project_name: str,
    environment: str,
) -> SecurityGroupResources:
    """Create the shared security group for Dagster services.

    Returns:
        SecurityGroupResources: Wrapper containing the security group resource.
    """
    security_group = ec2.SecurityGroup(
        resource_name,
        name=f"{project_name}-dagster-{environment}",
        description="Shared security group for Dagster services",
        vpc_id=vpc_id,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    dagster_ui_ingress = ec2.SecurityGroupRule(
        f"{resource_name}-ui-ingress",
        type="ingress",
        security_group_id=security_group.id,
        from_port=3000,
        to_port=3000,
        protocol="tcp",
        cidr_blocks=["0.0.0.0/0"],
        description="Dagster Web UI",
        opts=pulumi.ResourceOptions(provider=provider, parent=security_group),
    )

    postgres_ingress = ec2.SecurityGroupRule(
        f"{resource_name}-postgres-ingress",
        type="ingress",
        security_group_id=security_group.id,
        from_port=5432,
        to_port=5432,
        protocol="tcp",
        cidr_blocks=["10.0.0.0/8"],
        description="PostgreSQL access from LocalStack network",
        opts=pulumi.ResourceOptions(provider=provider, parent=security_group),
    )

    allow_all_egress = ec2.SecurityGroupRule(
        f"{resource_name}-egress",
        type="egress",
        security_group_id=security_group.id,
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        opts=pulumi.ResourceOptions(provider=provider, parent=security_group),
    )

    return SecurityGroupResources(
        security_group=security_group,
        ingress_rules=(dagster_ui_ingress, postgres_ingress),
        egress_rules=(allow_all_egress,),
    )
