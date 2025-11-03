"""Dagster module - bundles all Dagster-related infrastructure."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

import pulumi
from pulumi_aws import Provider, ec2, ecs, iam, lb, servicediscovery

from components.cloudwatch_logs import create_ecs_log_group
from components.ecs_helpers import (
    ContainerDefinition,
    HealthCheck,
    LogConfig,
    PortMapping,
    create_fargate_task_definition,
)


@dataclass
class DagsterResources:
    """All Dagster infrastructure resources."""

    security_group: ec2.SecurityGroup
    task_role: iam.Role
    daemon_task_definition: ecs.TaskDefinition
    webserver_task_definition: ecs.TaskDefinition
    daemon_log_group: pulumi.Resource
    webserver_log_group: pulumi.Resource
    service_discovery_namespace: servicediscovery.PrivateDnsNamespace
    daemon_service_discovery: servicediscovery.Service
    webserver_service_discovery: servicediscovery.Service
    load_balancer: lb.LoadBalancer
    dagster_target_group: lb.TargetGroup
    taskiq_target_group: lb.TargetGroup
    listener: lb.Listener
    taskiq_listener_rule: lb.ListenerRule


def create_dagster_infrastructure(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
    region: str,
    vpc_id: str,
    subnet_ids: Sequence[str],
    container_image: pulumi.Input[str],
    aws_endpoint_url: str,
    database_endpoint: pulumi.Input[str],
    queue_url: pulumi.Input[str],
    cluster_name: pulumi.Input[str],
    execution_role_arn: pulumi.Input[str],
) -> DagsterResources:
    """Create complete Dagster infrastructure including security, IAM, tasks, and load balancer.

    Args:
        resource_name: Base name for resources
        provider: AWS provider
        project_name: Project name for naming resources
        environment: Environment name (local, dev, prod)
        region: AWS region
        vpc_id: VPC ID for resources
        subnet_ids: Subnet IDs for load balancer
        container_image: Docker image for Dagster services
        aws_endpoint_url: AWS endpoint URL (for LocalStack)
        database_endpoint: PostgreSQL database endpoint
        queue_url: TaskIQ queue URL
        cluster_name: ECS cluster name
        execution_role_arn: ECS execution role ARN

    Returns:
        DagsterResources: Bundle of all created resources
    """
    # Create security group
    security_group = ec2.SecurityGroup(
        f"{resource_name}-sg",
        name=f"{project_name}-dagster-{environment}",
        description="Shared security group for Dagster services",
        vpc_id=vpc_id,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    ec2.SecurityGroupRule(
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

    ec2.SecurityGroupRule(
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

    ec2.SecurityGroupRule(
        f"{resource_name}-egress",
        type="egress",
        security_group_id=security_group.id,
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
        opts=pulumi.ResourceOptions(provider=provider, parent=security_group),
    )

    # Create CloudWatch log groups
    daemon_log_group = create_ecs_log_group(
        f"{resource_name}-daemon-logs",
        provider=provider,
        log_group_name=f"/aws/ecs/dagster-daemon-{environment}",
        retention_in_days=14,
    )

    webserver_log_group = create_ecs_log_group(
        f"{resource_name}-webserver-logs",
        provider=provider,
        log_group_name=f"/aws/ecs/dagster-webserver-{environment}",
        retention_in_days=14,
    )

    # Create IAM role for Dagster services
    assume_role_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
            }
        ],
    })

    task_role = iam.Role(
        f"{resource_name}-task-role",
        name=f"{project_name}-dagster-task-{environment}",
        assume_role_policy=assume_role_policy,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Attach Dagster-specific IAM permissions
    iam.RolePolicy(
        f"{resource_name}-inline-policy",
        role=task_role.id,
        policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "RDSAccess",
                    "Effect": "Allow",
                    "Action": [
                        "rds:DescribeDBInstances",
                        "rds:Connect",
                        "rds:DescribeDBClusters",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "ECSAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecs:DescribeServices",
                        "ecs:UpdateService",
                        "ecs:DescribeTasks",
                        "ecs:ListTasks",
                        "ecs:DescribeClusters",
                        "ecs:DescribeTaskDefinition",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "CloudWatchLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams",
                    ],
                    "Resource": "*",
                },
            ],
        }),
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Create task definitions
    def create_daemon_container(args: list[str]) -> list[ContainerDefinition]:
        db_endpoint, queue_url_val, cluster, image = args
        host = db_endpoint.split(":", maxsplit=1)[0]
        port = db_endpoint.split(":", maxsplit=1)[1] if ":" in db_endpoint else "5432"

        return [
            ContainerDefinition(
                name="dagster-daemon",
                image=image,
                environment={
                    "POSTGRES_HOST": host,
                    "POSTGRES_PORT": port,
                    "POSTGRES_USER": "dagster",
                    "POSTGRES_PASSWORD": "dagster",
                    "POSTGRES_DB": "dagster",
                    "AWS_ENDPOINT_URL": aws_endpoint_url,
                    "AWS_DEFAULT_REGION": region,
                    "DAGSTER_HOME": "/opt/dagster/dagster_home",
                    "PYTHONPATH": "/opt/dagster/app",
                    "TASKIQ_QUEUE_NAME": queue_url_val,
                    "ECS_CLUSTER_NAME": cluster,
                },
                health_check=HealthCheck(
                    command=["CMD-SHELL", "python -c \"import dagster; print('healthy')\" || exit 1"],
                    interval=30,
                    timeout=10,
                    retries=3,
                    start_period=120,
                ),
                log_config=LogConfig(log_group=f"/aws/ecs/dagster-daemon-{environment}", region=region),
                stop_timeout=120,
            )
        ]

    daemon_container_defs_json = pulumi.Output.all(database_endpoint, queue_url, cluster_name, container_image).apply(
        lambda args: json.dumps([c.to_dict() for c in create_daemon_container(args)])
    )

    daemon_task_definition = create_fargate_task_definition(
        f"{resource_name}-daemon-task",
        provider=provider,
        family=f"{project_name}-dagster-daemon-{environment}",
        container_definitions=daemon_container_defs_json,
        execution_role_arn=execution_role_arn,
        task_role_arn=task_role.arn,
        cpu="512",
        memory="1024",
    )

    def create_webserver_container(args: list[str]) -> list[ContainerDefinition]:
        db_endpoint, image = args
        host = db_endpoint.split(":", maxsplit=1)[0]
        port = db_endpoint.split(":", maxsplit=1)[1] if ":" in db_endpoint else "5432"

        return [
            ContainerDefinition(
                name="dagster-webserver",
                image=image,
                environment={
                    "POSTGRES_HOST": host,
                    "POSTGRES_PORT": port,
                    "POSTGRES_USER": "dagster",
                    "POSTGRES_PASSWORD": "dagster",
                    "POSTGRES_DB": "dagster",
                    "AWS_ENDPOINT_URL": aws_endpoint_url,
                    "AWS_DEFAULT_REGION": region,
                    "DAGSTER_HOME": "/opt/dagster/dagster_home",
                    "PYTHONPATH": "/opt/dagster/app",
                },
                port_mappings=[PortMapping(container_port=3000, name="dagster-web")],
                health_check=HealthCheck(
                    command=["CMD-SHELL", "curl -f http://localhost:3000/server_info || exit 1"],
                    interval=15,
                    timeout=5,
                    retries=3,
                    start_period=60,
                ),
                log_config=LogConfig(log_group=f"/aws/ecs/dagster-webserver-{environment}", region=region),
                stop_timeout=30,
            )
        ]

    webserver_container_defs_json = pulumi.Output.all(database_endpoint, container_image).apply(
        lambda args: json.dumps([c.to_dict() for c in create_webserver_container(args)])
    )

    webserver_task_definition = create_fargate_task_definition(
        f"{resource_name}-webserver-task",
        provider=provider,
        family=f"{project_name}-dagster-webserver-{environment}",
        container_definitions=webserver_container_defs_json,
        execution_role_arn=execution_role_arn,
        task_role_arn=task_role.arn,
        cpu="512",
        memory="1024",
    )

    # Create service discovery
    namespace = servicediscovery.PrivateDnsNamespace(
        f"{resource_name}-namespace",
        name=f"{project_name}-{environment}.local",
        vpc=vpc_id,
        description="Service discovery namespace for Dagster services",
        opts=pulumi.ResourceOptions(provider=provider),
    )

    daemon_service_discovery = servicediscovery.Service(
        f"{resource_name}-daemon-discovery",
        name="dagster-daemon",
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
        opts=pulumi.ResourceOptions(provider=provider),
    )

    webserver_service_discovery = servicediscovery.Service(
        f"{resource_name}-webserver-discovery",
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
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Create load balancer
    load_balancer = lb.LoadBalancer(
        f"{resource_name}-alb",
        name=f"{project_name}-alb-{environment}",
        load_balancer_type="application",
        subnets=list(subnet_ids),
        security_groups=pulumi.Output.from_input(security_group.id).apply(lambda sg: [sg]),
        internal=False,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Target group for Dagster webserver
    dagster_target_group = lb.TargetGroup(
        f"{resource_name}-dagster-tg",
        name=f"{project_name}-dagster-tg-{environment}",
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
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Target group for TaskIQ demo API
    taskiq_target_group = lb.TargetGroup(
        f"{resource_name}-taskiq-tg",
        name=f"{project_name}-taskiq-tg-{environment}",
        port=8000,
        protocol="HTTP",
        vpc_id=vpc_id,
        target_type="ip",
        health_check=lb.TargetGroupHealthCheckArgs(
            enabled=True,
            healthy_threshold=2,
            interval=30,
            matcher="200",
            path="/health",
            port="traffic-port",
            protocol="HTTP",
            timeout=5,
            unhealthy_threshold=2,
        ),
        opts=pulumi.ResourceOptions(provider=provider),
    )

    listener = lb.Listener(
        f"{resource_name}-listener",
        load_balancer_arn=load_balancer.arn,
        port=80,
        protocol="HTTP",
        default_actions=[
            lb.ListenerDefaultActionArgs(
                type="forward",
                target_group_arn=dagster_target_group.arn,
            )
        ],
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Listener rule for TaskIQ demo API (path-based routing)
    taskiq_listener_rule = lb.ListenerRule(
        f"{resource_name}-taskiq-rule",
        listener_arn=listener.arn,
        priority=10,
        conditions=[
            lb.ListenerRuleConditionArgs(
                path_pattern=lb.ListenerRuleConditionPathPatternArgs(
                    values=["/api/*"],
                ),
            ),
        ],
        actions=[
            lb.ListenerRuleActionArgs(
                type="forward",
                target_group_arn=taskiq_target_group.arn,
            ),
        ],
        opts=pulumi.ResourceOptions(provider=provider),
    )

    return DagsterResources(
        security_group=security_group,
        task_role=task_role,
        daemon_task_definition=daemon_task_definition,
        webserver_task_definition=webserver_task_definition,
        daemon_log_group=daemon_log_group,
        webserver_log_group=webserver_log_group,
        service_discovery_namespace=namespace,
        daemon_service_discovery=daemon_service_discovery,
        webserver_service_discovery=webserver_service_discovery,
        load_balancer=load_balancer,
        dagster_target_group=dagster_target_group,
        taskiq_target_group=taskiq_target_group,
        listener=listener,
        taskiq_listener_rule=taskiq_listener_rule,
    )
