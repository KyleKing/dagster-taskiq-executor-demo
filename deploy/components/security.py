"""Security group definitions for Dagster services."""

from dataclasses import dataclass

from pulumi import ResourceOptions
from pulumi_aws import Provider, ec2


@dataclass
class SecurityGroupResources:
    """Outputs for the Dagster shared security group."""

    security_group: ec2.SecurityGroup


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
        ingress=[
            ec2.SecurityGroupIngressArgs(
                from_port=3000,
                to_port=3000,
                protocol="tcp",
                cidr_blocks=["0.0.0.0/0"],
                description="Dagster Web UI",
            ),
            ec2.SecurityGroupIngressArgs(
                from_port=5432,
                to_port=5432,
                protocol="tcp",
                cidr_blocks=["10.0.0.0/8"],
                description="PostgreSQL access from LocalStack network",
            ),
        ],
        egress=[
            ec2.SecurityGroupEgressArgs(
                from_port=0,
                to_port=0,
                protocol="-1",
                cidr_blocks=["0.0.0.0/0"],
            )
        ],
        opts=ResourceOptions(provider=provider),
    )
    return SecurityGroupResources(security_group=security_group)
