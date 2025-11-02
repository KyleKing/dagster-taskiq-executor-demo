"""Pulumi program that provisions the Dagster + TaskIQ LocalStack infrastructure."""

from __future__ import annotations

import json

import pulumi
import pulumi_aws as aws
from pulumi_aws import ec2, iam

from components.aurora_postgres import create_postgres_database
from components.container_image import create_container_image
from components.ecs_cluster import create_ecs_cluster
from components.network import fetch_default_network
from components.provider import LocalStackProviderConfig, create_localstack_provider
from config import StackSettings
from modules.dagster import create_dagster_infrastructure
from modules.taskiq import create_taskiq_infrastructure


def main() -> None:
    """Provision the Dagster TaskIQ infrastructure on LocalStack."""
    settings = StackSettings.load()

    # Create LocalStack provider
    provider = create_localstack_provider(
        "localstack",
        LocalStackProviderConfig(
            region=settings.aws.region,
            endpoint=settings.aws.endpoint,
            access_key=settings.aws.access_key,
            secret_key=settings.aws.secret_key,
        ),
    )

    # Fetch networking resources
    network = fetch_default_network(provider=provider)

    # Create shared ECS execution role
    execution_role = iam.Role(
        "ecs-execution-role",
        name=f"{settings.project.name}-ecs-execution-{settings.project.environment}",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                }
            ],
        }),
        opts=pulumi.ResourceOptions(provider=provider),
    )

    iam.RolePolicyAttachment(
        "ecs-execution-policy",
        role=execution_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Build and push container image
    container_image = create_container_image(
        "dagster-taskiq",
        provider=provider,
        project_name=settings.project.name,
        environment=settings.project.environment,
        context_path="../app",
        dockerfile_path="../app/Dockerfile",
        platform="linux/amd64",
    )

    # Create ECS cluster
    cluster = create_ecs_cluster(
        "dagster-cluster",
        provider=provider,
        project_name=settings.project.name,
        environment=settings.project.environment,
    )

    # Create PostgreSQL database first (with placeholder security group)
    # We'll create the security group separately
    # Create security group for database access
    db_security_group = ec2.SecurityGroup(
        "dagster-db-sg",
        name=f"{settings.project.name}-db-{settings.project.environment}",
        description="Security group for PostgreSQL database",
        vpc_id=network.vpc.id,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    ec2.SecurityGroupRule(
        "db-postgres-ingress",
        type="ingress",
        security_group_id=db_security_group.id,
        from_port=5432,
        to_port=5432,
        protocol="tcp",
        cidr_blocks=["10.0.0.0/8"],
        description="PostgreSQL access from LocalStack network",
        opts=pulumi.ResourceOptions(provider=provider, parent=db_security_group),
    )

    database = create_postgres_database(
        "dagster-db",
        provider=provider,
        subnet_ids=network.subnets.ids,
        security_group_ids=[db_security_group.id],
        db_name=settings.database.db_name,
        username=settings.database.username,
        password=settings.database.password,
        project_name=settings.project.name,
        environment=settings.project.environment,
        engine_version=settings.database.engine_version,
        min_capacity=settings.database.min_capacity,
        max_capacity=settings.database.max_capacity,
        publicly_accessible=settings.database.publicly_accessible,
        deletion_protection=settings.database.deletion_protection,
        backup_retention_period=settings.database.backup_retention_period,
    )

    # Create TaskIQ infrastructure module
    taskiq = create_taskiq_infrastructure(
        "taskiq",
        provider=provider,
        project_name=settings.project.name,
        environment=settings.project.environment,
        region=settings.aws.region,
        container_image=container_image.image_uri,
        aws_endpoint_url=settings.aws.endpoint,
        database_endpoint=database.cluster.endpoint,
        execution_role_arn=execution_role.arn,
        message_retention_seconds=settings.queue.message_retention_seconds,
        queue_visibility_timeout=settings.queue.visibility_timeout,
        dlq_visibility_timeout=settings.queue.dlq_visibility_timeout,
        redrive_max_receive_count=settings.queue.redrive_max_receive_count,
    )

    # Create Dagster infrastructure module
    dagster = create_dagster_infrastructure(
        "dagster",
        provider=provider,
        project_name=settings.project.name,
        environment=settings.project.environment,
        region=settings.aws.region,
        vpc_id=network.vpc.id,
        subnet_ids=network.subnets.ids,
        container_image=container_image.image_uri,
        aws_endpoint_url=settings.aws.endpoint,
        database_endpoint=database.cluster.endpoint,
        queue_url=taskiq.queues.queue.id,
        cluster_name=cluster.cluster.name,
        execution_role_arn=execution_role.arn,
    )

    # Create ECS services
    security_group_output = pulumi.Output.from_input(dagster.security_group.id).apply(lambda sg: [sg])

    dagster_daemon_service = aws.ecs.Service(
        "dagster-daemon-service",
        aws.ecs.ServiceArgs(
            name=f"{settings.project.name}-daemon-{settings.project.environment}",
            cluster=cluster.cluster.id,
            task_definition=dagster.daemon_task_definition.arn,
            desired_count=settings.services.daemon_desired_count,
            launch_type="FARGATE",
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                subnets=network.subnets.ids,
                security_groups=security_group_output,
                assign_public_ip=True,
            ),
            service_registries=aws.ecs.ServiceServiceRegistriesArgs(
                registry_arn=dagster.daemon_service_discovery.arn,
            ),
        ),
        opts=pulumi.ResourceOptions(provider=provider),
    )

    dagster_webserver_service = aws.ecs.Service(
        "dagster-webserver-service",
        aws.ecs.ServiceArgs(
            name=f"{settings.project.name}-webserver-{settings.project.environment}",
            cluster=cluster.cluster.id,
            task_definition=dagster.webserver_task_definition.arn,
            desired_count=settings.services.webserver_desired_count,
            launch_type="FARGATE",
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                subnets=network.subnets.ids,
                security_groups=security_group_output,
                assign_public_ip=True,
            ),
            load_balancers=[
                aws.ecs.ServiceLoadBalancerArgs(
                    target_group_arn=dagster.target_group.arn,
                    container_name="dagster-webserver",
                    container_port=3000,
                )
            ],
            service_registries=aws.ecs.ServiceServiceRegistriesArgs(
                registry_arn=dagster.webserver_service_discovery.arn,
            ),
        ),
        opts=pulumi.ResourceOptions(provider=provider, depends_on=[dagster.listener]),
    )

    taskiq_worker_service = aws.ecs.Service(
        "taskiq-worker-service",
        aws.ecs.ServiceArgs(
            name=f"{settings.project.name}-workers-{settings.project.environment}",
            cluster=cluster.cluster.id,
            task_definition=taskiq.worker_task_definition.arn,
            desired_count=settings.services.worker_desired_count,
            launch_type="FARGATE",
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                subnets=network.subnets.ids,
                security_groups=security_group_output,
                assign_public_ip=True,
            ),
        ),
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Stack outputs to simplify debugging and downstream configuration.
    pulumi.export("container_image_uri", container_image.image_uri)
    pulumi.export("ecr_repository_url", container_image.repository.repository_url)
    pulumi.export("queue_url", taskiq.queues.queue.id)
    pulumi.export("queue_arn", taskiq.queues.queue.arn)
    pulumi.export("dlq_url", taskiq.queues.dead_letter_queue.id)
    pulumi.export("dlq_arn", taskiq.queues.dead_letter_queue.arn)
    pulumi.export("cluster_arn", cluster.cluster.arn)
    pulumi.export("cluster_name", cluster.cluster.name)
    pulumi.export("dagster_task_role_arn", dagster.task_role.arn)
    pulumi.export("taskiq_task_role_arn", taskiq.task_role.arn)
    pulumi.export("execution_role_arn", execution_role.arn)
    pulumi.export("security_group_id", dagster.security_group.id)
    pulumi.export("vpc_id", network.vpc.id)
    pulumi.export("subnet_ids", network.subnets.ids)
    pulumi.export("aurora_cluster_endpoint", database.cluster.endpoint)
    pulumi.export("aurora_reader_endpoint", database.cluster.reader_endpoint)
    pulumi.export("aurora_port", database.cluster.port)
    pulumi.export("aurora_db_name", database.cluster.database_name)
    pulumi.export("alb_dns_name", dagster.load_balancer.dns_name)
    pulumi.export("alb_zone_id", dagster.load_balancer.zone_id)
    pulumi.export("service_discovery_namespace", dagster.service_discovery_namespace.name)
    pulumi.export("dagster_daemon_service_name", dagster_daemon_service.name)
    pulumi.export("dagster_webserver_service_name", dagster_webserver_service.name)
    pulumi.export("taskiq_worker_service_name", taskiq_worker_service.name)
    pulumi.export("dagster_web_url", pulumi.Output.concat("http://", dagster.load_balancer.dns_name))


main()
