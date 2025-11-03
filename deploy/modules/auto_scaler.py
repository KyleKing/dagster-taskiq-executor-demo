"""Auto-scaler module - bundles all auto-scaler infrastructure."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import cast

import pulumi
from pulumi_aws import Provider, ecs, iam

from components.cloudwatch_logs import create_ecs_log_group
from components.ecs_helpers import (
    ContainerDefinition,
    HealthCheck,
    LogConfig,
    create_fargate_task_definition,
)


@dataclass
class AutoScalerResources:
    """All auto-scaler infrastructure resources."""

    task_role: iam.Role
    task_definition: ecs.TaskDefinition
    log_group: pulumi.Resource


def create_auto_scaler_infrastructure(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
    region: str,
    container_image: pulumi.Input[str],
    aws_endpoint_url: str,
    database_endpoint: pulumi.Input[str],
    queue_url: pulumi.Input[str],
    cluster_name: pulumi.Input[str],
    worker_service_name: str,
    execution_role_arn: pulumi.Input[str],
) -> AutoScalerResources:
    """Create complete auto-scaler infrastructure including IAM and task definitions.

    Args:
        resource_name: Base name for resources
        provider: AWS provider
        project_name: Project name for naming resources
        environment: Environment name (local, dev, prod)
        region: AWS region
        container_image: Docker image for auto-scaler
        aws_endpoint_url: AWS endpoint URL (for LocalStack)
        database_endpoint: PostgreSQL database endpoint
        queue_url: TaskIQ queue URL
        cluster_name: ECS cluster name
        worker_service_name: Name of the worker service to scale
        execution_role_arn: ECS execution role ARN

    Returns:
        AutoScalerResources: Bundle of all created resources
    """
    # Create IAM role for auto-scaler
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
        name=f"{project_name}-auto-scaler-task-{environment}",
        assume_role_policy=assume_role_policy,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Attach auto-scaler-specific IAM permissions
    inline_policy = pulumi.Output.all(queue_url, cluster_name).apply(
        lambda args: json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "SQSAccess",
                    "Effect": "Allow",
                    "Action": [
                        "sqs:GetQueueAttributes",
                        "sqs:ListQueues",
                    ],
                    "Resource": f"arn:aws:sqs:{region}:000000000000/{args[0].split('/')[-1]}",
                },
                {
                    "Sid": "ECSAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecs:DescribeServices",
                        "ecs:UpdateService",
                        "ecs:DescribeTasks",
                        "ecs:ListTasks",
                        "ecs:StopTask",
                        "ecs:DescribeClusters",
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
        })
    )

    iam.RolePolicy(
        f"{resource_name}-inline-policy",
        role=task_role.id,
        policy=inline_policy,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Create CloudWatch log group
    log_group = create_ecs_log_group(
        f"{resource_name}-logs",
        provider=provider,
        log_group_name=f"/aws/ecs/auto-scaler-{environment}",
        retention_in_days=14,
    )

    # Create task definition
    def create_auto_scaler_container(args: tuple[str, str, str, str, str]) -> list[ContainerDefinition]:
        db_endpoint, queue_name, cluster, worker_svc, image = args
        host = db_endpoint.split(":", maxsplit=1)[0]

        return [
            ContainerDefinition(
                name="auto-scaler",
                image=image,
                command=["python", "-m", "dagster_taskiq.auto_scaler.service"],
                environment={
                    "POSTGRES_HOST": host,
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_USER": "dagster",
                    "POSTGRES_PASSWORD": "dagster",
                    "POSTGRES_DB": "dagster",
                    "AWS_ENDPOINT_URL": aws_endpoint_url,
                    "AWS_DEFAULT_REGION": region,
                    "DAGSTER_HOME": "/opt/dagster/dagster_home",
                    "PYTHONPATH": "/opt/dagster/app",
                    "TASKIQ_QUEUE_NAME": queue_name,
                    "ECS_CLUSTER_NAME": cluster,
                    "ECS_WORKER_SERVICE_NAME": worker_svc,
                    "AUTOSCALER_MIN_WORKERS": "2",
                    "AUTOSCALER_MAX_WORKERS": "20",
                    "AUTOSCALER_SCALE_UP_THRESHOLD": "5",
                    "AUTOSCALER_SCALE_DOWN_THRESHOLD": "2",
                    "AUTOSCALER_COOLDOWN_SECONDS": "60",
                },
                health_check=HealthCheck(
                    command=["CMD-SHELL", "curl -f http://localhost:8081/healthz || exit 1"],
                    interval=30,
                    timeout=10,
                    retries=2,
                    start_period=30,
                ),
                log_config=LogConfig(log_group=f"/aws/ecs/auto-scaler-{environment}", region=region),
                stop_timeout=30,
            )
        ]

    def _serialize_containers(args: tuple[str, str, str, str, str]) -> str:
        return json.dumps([c.to_dict() for c in create_auto_scaler_container(args)])

    # Extract queue name from URL
    queue_name = pulumi.Output.from_input(queue_url).apply(lambda url: url.split("/")[-1])

    container_defs_json = pulumi.Output.all(
        database_endpoint, queue_name, cluster_name, worker_service_name, container_image
    ).apply(lambda args: _serialize_containers(cast("tuple[str, str, str, str, str]", tuple(args))))

    task_definition = create_fargate_task_definition(
        f"{resource_name}-task",
        provider=provider,
        family=f"{project_name}-auto-scaler-{environment}",
        container_definitions=container_defs_json,
        execution_role_arn=execution_role_arn,
        task_role_arn=task_role.arn,
        cpu="256",
        memory="512",
    )

    return AutoScalerResources(
        task_role=task_role,
        task_definition=task_definition,
        log_group=log_group,
    )
