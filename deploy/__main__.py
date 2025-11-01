"""Pulumi program that provisions the Dagster + TaskIQ LocalStack infrastructure."""

from __future__ import annotations

import pulumi
import pulumi_aws as aws
from pulumi import ResourceOptions

from components.ecs_cluster import create_ecs_cluster
from components.iam import create_ecs_iam_roles
from components.load_balancer import create_load_balancer
from components.network import fetch_default_network
from components.provider import LocalStackProviderConfig, create_localstack_provider
from components.rds_postgres import create_postgres_database
from components.security import create_dagster_security_group
from components.service_discovery import create_service_discovery
from components.sqs_fifo import attach_queue_access_policy, create_fifo_queue_with_dlq
from components.task_definitions import create_task_definitions
from config import StackSettings


def main() -> None:
    """Provision the Dagster TaskIQ infrastructure on LocalStack."""
    settings = StackSettings.load()

    provider = create_localstack_provider(
        "localstack",
        LocalStackProviderConfig(
            region=settings.aws.region,
            endpoint=settings.aws.endpoint,
            access_key=settings.aws.access_key,
            secret_key=settings.aws.secret_key,
        ),
    )

    network = fetch_default_network(provider=provider)

    security_group = create_dagster_security_group(
        "dagster-sg",
        provider=provider,
        vpc_id=network.vpc.id,
        project_name=settings.project.name,
        environment=settings.project.environment,
    )

    queues = create_fifo_queue_with_dlq(
        "taskiq",
        provider=provider,
        queue_name=f"{settings.project.name}-taskiq-{settings.project.environment}.fifo",
        dlq_name=f"{settings.project.name}-taskiq-dlq-{settings.project.environment}.fifo",
        message_retention_seconds=settings.queue.message_retention_seconds,
        queue_visibility_timeout=settings.queue.visibility_timeout,
        dlq_visibility_timeout=settings.queue.dlq_visibility_timeout,
        redrive_max_receive_count=settings.queue.redrive_max_receive_count,
    )

    iam_roles = create_ecs_iam_roles(
        "ecs-iam",
        provider=provider,
        project_name=settings.project.name,
        environment=settings.project.environment,
        queue_arn=queues.queue.arn,
        dlq_arn=queues.dead_letter_queue.arn,
    )

    attach_queue_access_policy(
        "taskiq",
        provider=provider,
        queues=queues,
        principal_arns=pulumi.Output.from_input(iam_roles.task_role.arn).apply(lambda arn: [arn]),
        actions=[
            "sqs:SendMessage",
            "sqs:ReceiveMessage",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes",
            "sqs:ChangeMessageVisibility",
        ],
    )

    security_group_output = pulumi.Output.from_input(security_group.security_group.id).apply(lambda sg: [sg])

    database = create_postgres_database(
        "dagster-db",
        provider=provider,
        subnet_ids=network.subnets.ids,
        security_group_ids=[security_group.security_group.id],
        db_name=settings.database.db_name,
        username=settings.database.username,
        password=settings.database.password,
        instance_class=settings.database.instance_class,
        allocated_storage=settings.database.allocated_storage,
        max_allocated_storage=settings.database.max_allocated_storage,
        engine_version=settings.database.engine_version,
        project_name=settings.project.name,
        environment=settings.project.environment,
    )

    cluster = create_ecs_cluster(
        "dagster-cluster",
        provider=provider,
        project_name=settings.project.name,
        environment=settings.project.environment,
    )

    tasks = create_task_definitions(
        "dagster-tasks",
        provider=provider,
        project_name=settings.project.name,
        environment=settings.project.environment,
        region=settings.aws.region,
        container_image=settings.services.image,
        aws_endpoint_url=settings.aws.endpoint,
        database_endpoint=database.instance.endpoint,
        queue_url=queues.queue.id,
        dlq_url=queues.dead_letter_queue.id,
        cluster_name=cluster.cluster.name,
        execution_role_arn=iam_roles.execution_role.arn,
        task_role_arn=iam_roles.task_role.arn,
    )

    service_discovery = create_service_discovery(
        "dagster-discovery",
        provider=provider,
        project_name=settings.project.name,
        environment=settings.project.environment,
        vpc_id=network.vpc.id,
    )

    load_balancer = create_load_balancer(
        "dagster-alb",
        provider=provider,
        project_name=settings.project.name,
        environment=settings.project.environment,
        subnet_ids=network.subnets.ids,
        security_group_ids=[security_group.security_group.id],
        vpc_id=network.vpc.id,
    )

    dagster_daemon_service = aws.ecs.Service(
        "dagster-daemon-service",
        aws.ecs.ServiceArgs(
            name=f"{settings.project.name}-daemon-{settings.project.environment}",
            cluster=cluster.cluster.id,
            task_definition=tasks.dagster_daemon.arn,
            desired_count=settings.services.daemon_desired_count,
            launch_type="FARGATE",
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                subnets=network.subnets.ids,
                security_groups=security_group_output,
                assign_public_ip=True,
            ),
            service_registries=aws.ecs.ServiceServiceRegistriesArgs(
                registry_arn=service_discovery.namespace.arn,
            ),
        ),
        opts=ResourceOptions(provider=provider),
    )

    dagster_webserver_service = aws.ecs.Service(
        "dagster-webserver-service",
        aws.ecs.ServiceArgs(
            name=f"{settings.project.name}-webserver-{settings.project.environment}",
            cluster=cluster.cluster.id,
            task_definition=tasks.dagster_webserver.arn,
            desired_count=settings.services.webserver_desired_count,
            launch_type="FARGATE",
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                subnets=network.subnets.ids,
                security_groups=security_group_output,
                assign_public_ip=True,
            ),
            load_balancers=[
                aws.ecs.ServiceLoadBalancerArgs(
                    target_group_arn=load_balancer.target_group.arn,
                    container_name="dagster-webserver",
                    container_port=3000,
                )
            ],
            service_registries=aws.ecs.ServiceServiceRegistriesArgs(
                registry_arn=service_discovery.webserver_service.arn,
            ),
        ),
        opts=ResourceOptions(provider=provider, depends_on=[load_balancer.listener]),
    )

    taskiq_worker_service = aws.ecs.Service(
        "taskiq-worker-service",
        aws.ecs.ServiceArgs(
            name=f"{settings.project.name}-workers-{settings.project.environment}",
            cluster=cluster.cluster.id,
            task_definition=tasks.taskiq_worker.arn,
            desired_count=settings.services.worker_desired_count,
            launch_type="FARGATE",
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                subnets=network.subnets.ids,
                security_groups=security_group_output,
                assign_public_ip=True,
            ),
        ),
        opts=ResourceOptions(provider=provider),
    )

    # Stack outputs to simplify debugging and downstream configuration.
    pulumi.export("queue_url", queues.queue.id)
    pulumi.export("queue_arn", queues.queue.arn)
    pulumi.export("dlq_url", queues.dead_letter_queue.id)
    pulumi.export("dlq_arn", queues.dead_letter_queue.arn)
    pulumi.export("cluster_arn", cluster.cluster.arn)
    pulumi.export("cluster_name", cluster.cluster.name)
    pulumi.export("task_role_arn", iam_roles.task_role.arn)
    pulumi.export("execution_role_arn", iam_roles.execution_role.arn)
    pulumi.export("security_group_id", security_group.security_group.id)
    pulumi.export("vpc_id", network.vpc.id)
    pulumi.export("subnet_ids", network.subnets.ids)
    pulumi.export("rds_endpoint", database.instance.endpoint)
    pulumi.export("rds_port", database.instance.port)
    pulumi.export("rds_db_name", database.instance.db_name)
    pulumi.export("alb_dns_name", load_balancer.load_balancer.dns_name)
    pulumi.export("alb_zone_id", load_balancer.load_balancer.zone_id)
    pulumi.export("service_discovery_namespace", service_discovery.namespace.name)
    pulumi.export("dagster_daemon_service_name", dagster_daemon_service.name)
    pulumi.export("dagster_webserver_service_name", dagster_webserver_service.name)
    pulumi.export("taskiq_worker_service_name", taskiq_worker_service.name)
    pulumi.export("dagster_web_url", pulumi.Output.concat("http://", load_balancer.load_balancer.dns_name))


main()
