"""ECS cluster component for Dagster services."""

from dataclasses import dataclass

from pulumi import ResourceOptions
from pulumi_aws import Provider, ecs


@dataclass
class ClusterResources:
    """Outputs for the Dagster ECS cluster."""

    cluster: ecs.Cluster


def create_ecs_cluster(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
) -> ClusterResources:
    """Provision the ECS cluster with execute-command support.

    Returns:
        ClusterResources: Wrapper containing the created ECS cluster.
    """
    cluster = ecs.Cluster(
        f"{resource_name}-cluster",
        name=f"{project_name}-{environment}",
        settings=[
            ecs.ClusterSettingArgs(
                name="containerInsights",
                value="enabled",
            )
        ],
        configuration=ecs.ClusterConfigurationArgs(
            execute_command_configuration=ecs.ClusterConfigurationExecuteCommandConfigurationArgs(
                logging="DEFAULT",
            )
        ),
        opts=ResourceOptions(provider=provider),
    )

    return ClusterResources(cluster=cluster)
