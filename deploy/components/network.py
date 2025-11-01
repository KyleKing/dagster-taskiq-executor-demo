"""Networking helpers for the infrastructure stack."""

from dataclasses import dataclass

import pulumi
from pulumi_aws import Provider, ec2


@dataclass
class NetworkResources:
    """Outputs from fetching the default network."""

    vpc: ec2.GetVpcResult
    subnets: ec2.GetSubnetsResult


def fetch_default_network(*, provider: Provider) -> NetworkResources:
    """Return the default VPC and subnet set provided by LocalStack.

    Returns:
        NetworkResources: Wrapper containing VPC and subnet metadata.
    """
    invoke_opts = pulumi.InvokeOptions(provider=provider)
    vpc = ec2.get_vpc(default=True, opts=invoke_opts)
    subnets = ec2.get_subnets(
        filters=[ec2.GetSubnetsFilterArgs(name="vpc-id", values=[vpc.id])],
        opts=invoke_opts,
    )
    return NetworkResources(vpc=vpc, subnets=subnets)
