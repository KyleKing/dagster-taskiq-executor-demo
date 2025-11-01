"""Service discovery utilities for ECS services."""

from dataclasses import dataclass

from pulumi import ResourceOptions
from pulumi_aws import Provider, servicediscovery


@dataclass
class ServiceDiscoveryResources:
    """Outputs for the Cloud Map namespace and services."""

    namespace: servicediscovery.PrivateDnsNamespace
    webserver_service: servicediscovery.Service


def create_service_discovery(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
    vpc_id: str,
) -> ServiceDiscoveryResources:
    """Configure Cloud Map namespace and Dagster webserver service discovery.

    Returns:
        ServiceDiscoveryResources: Wrapper containing namespace references.
    """
    namespace = servicediscovery.PrivateDnsNamespace(
        f"{resource_name}-namespace",
        name=f"{project_name}-{environment}.local",
        vpc=vpc_id,
        description="Service discovery namespace for Dagster services",
        opts=ResourceOptions(provider=provider),
    )

    webserver_service = servicediscovery.Service(
        f"{resource_name}-webserver",
        name="dagster-webserver",
        namespace_id=namespace.id,
        dns_config=servicediscovery.ServiceDnsConfigArgs(
            namespace_id=namespace.id,
            dns_records=[
                servicediscovery.ServiceDnsConfigDnsRecordArgs(
                    ttl=10,
                    type="A",
                )
            ],
            routing_policy="MULTIVALUE",
        ),
        opts=ResourceOptions(provider=provider),
    )

    return ServiceDiscoveryResources(namespace=namespace, webserver_service=webserver_service)
