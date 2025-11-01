"""Application Load Balancer for the Dagster web UI."""

from collections.abc import Sequence
from dataclasses import dataclass

from pulumi import Input, ResourceOptions
from pulumi_aws import Provider, lb


@dataclass
class LoadBalancerResources:
    """Outputs for the Dagster load balancing layer."""

    load_balancer: lb.LoadBalancer
    target_group: lb.TargetGroup
    listener: lb.Listener


def create_load_balancer(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
    subnet_ids: Sequence[str],
    security_group_ids: Sequence[Input[str]],
    vpc_id: str,
) -> LoadBalancerResources:
    """Provision an ALB, target group, and listener for the Dagster webserver.

    Returns:
        LoadBalancerResources: Wrapper containing ALB components.
    """
    load_balancer = lb.LoadBalancer(
        f"{resource_name}-alb",
        name=f"{project_name}-alb-{environment}",
        load_balancer_type="application",
        subnets=list(subnet_ids),
        security_groups=security_group_ids,
        internal=False,
        opts=ResourceOptions(provider=provider),
    )

    target_group = lb.TargetGroup(
        f"{resource_name}-tg",
        name=f"{project_name}-tg-{environment}",
        port=3000,
        protocol="HTTP",
        vpc_id=vpc_id,
        target_type="ip",
        health_check=lb.TargetGroupHealthCheckArgs(
            enabled=True,
            healthy_threshold=2,
            interval=30,
            matcher="200",
            path="/server_info",
            port="traffic-port",
            protocol="HTTP",
            timeout=5,
            unhealthy_threshold=2,
        ),
        opts=ResourceOptions(provider=provider),
    )

    listener = lb.Listener(
        f"{resource_name}-listener",
        load_balancer_arn=load_balancer.arn,
        port=80,
        protocol="HTTP",
        default_actions=[
            lb.ListenerDefaultActionArgs(
                type="forward",
                target_group_arn=target_group.arn,
            )
        ],
        opts=ResourceOptions(provider=provider),
    )

    return LoadBalancerResources(
        load_balancer=load_balancer,
        target_group=target_group,
        listener=listener,
    )
