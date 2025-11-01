"""ECS task definitions for Dagster and TaskIQ services."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pulumi
from pulumi import ResourceOptions
from pulumi_aws import Provider, ecs


@dataclass
class TaskDefinitions:
    """Outputs for the ECS task definitions."""

    dagster_daemon: ecs.TaskDefinition
    dagster_webserver: ecs.TaskDefinition
    taskiq_worker: ecs.TaskDefinition


def create_task_definitions(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
    region: str,
    container_image: str,
    aws_endpoint_url: str,
    database_endpoint: pulumi.Input[str],
    queue_url: pulumi.Input[str],
    dlq_url: pulumi.Input[str],
    cluster_name: pulumi.Input[str],
    execution_role_arn: pulumi.Input[str],
    task_role_arn: pulumi.Input[str],
) -> TaskDefinitions:
    """Create ECS task definitions used by the stack.

    Returns:
        TaskDefinitions: Wrapper containing all ECS task definitions.
    """

    def _base_env(db_endpoint: str) -> list[dict[str, str]]:
        host = db_endpoint.split(":", maxsplit=1)[0]
        return [
            {"name": "POSTGRES_HOST", "value": host},
            {"name": "POSTGRES_PORT", "value": "5432"},
            {"name": "POSTGRES_USER", "value": "dagster"},
            {"name": "POSTGRES_PASSWORD", "value": "dagster"},
            {"name": "POSTGRES_DB", "value": "dagster"},
            {"name": "AWS_ENDPOINT_URL", "value": aws_endpoint_url},
            {"name": "AWS_DEFAULT_REGION", "value": region},
            {"name": "DAGSTER_HOME", "value": "/opt/dagster/dagster_home"},
            {"name": "PYTHONPATH", "value": "/opt/dagster/app"},
        ]

    database_output = pulumi.Output.from_input(database_endpoint)

    daemon_definitions = pulumi.Output.all(database_output, queue_url, cluster_name).apply(
        lambda args: json.dumps([
            {
                "name": "dagster-daemon",
                "image": container_image,
                "essential": True,
                "environment": [
                    *_base_env(args[0]),
                    {"name": "TASKIQ_QUEUE_NAME", "value": args[1]},
                    {"name": "ECS_CLUSTER_NAME", "value": args[2]},
                ],
                "healthCheck": {
                    "command": ["CMD-SHELL", "python -c \"import dagster; print('healthy')\""],
                    "interval": 30,
                    "timeout": 5,
                    "retries": 3,
                    "startPeriod": 60,
                },
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/aws/ecs/dagster-daemon",
                        "awslogs-region": region,
                        "awslogs-stream-prefix": "ecs",
                        "awslogs-create-group": "true",
                    },
                },
                "stopTimeout": 120,
            }
        ])
    )

    dagster_daemon = ecs.TaskDefinition(
        f"{resource_name}-daemon",
        family=f"{project_name}-dagster-daemon-{environment}",
        network_mode="awsvpc",
        requires_compatibilities=["FARGATE"],
        cpu="512",
        memory="1024",
        execution_role_arn=execution_role_arn,
        task_role_arn=task_role_arn,
        container_definitions=daemon_definitions,
        opts=ResourceOptions(provider=provider),
    )

    webserver_definitions = database_output.apply(
        lambda endpoint: json.dumps([
            {
                "name": "dagster-webserver",
                "image": container_image,
                "essential": True,
                "portMappings": [
                    {
                        "containerPort": 3000,
                        "protocol": "tcp",
                        "name": "dagster-web",
                    }
                ],
                "environment": _base_env(endpoint),
                "healthCheck": {
                    "command": ["CMD-SHELL", "curl -f http://localhost:3000/server_info || exit 1"],
                    "interval": 30,
                    "timeout": 5,
                    "retries": 3,
                    "startPeriod": 60,
                },
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/aws/ecs/dagster-webserver",
                        "awslogs-region": region,
                        "awslogs-stream-prefix": "ecs",
                        "awslogs-create-group": "true",
                    },
                },
                "stopTimeout": 30,
            }
        ])
    )

    dagster_webserver = ecs.TaskDefinition(
        f"{resource_name}-webserver",
        family=f"{project_name}-dagster-webserver-{environment}",
        network_mode="awsvpc",
        requires_compatibilities=["FARGATE"],
        cpu="512",
        memory="1024",
        execution_role_arn=execution_role_arn,
        task_role_arn=task_role_arn,
        container_definitions=webserver_definitions,
        opts=ResourceOptions(provider=provider),
    )

    worker_definitions = pulumi.Output.all(database_output, queue_url, dlq_url).apply(
        lambda args: json.dumps([
            {
                "name": "taskiq-worker",
                "image": container_image,
                "essential": True,
                "environment": [
                    *_base_env(args[0]),
                    {"name": "TASKIQ_QUEUE_NAME", "value": args[1]},
                    {"name": "TASKIQ_DLQ_NAME", "value": args[2]},
                    {"name": "WORKER_CONCURRENCY", "value": "2"},
                    {"name": "TASKIQ_WORKER_ID", "value": "worker-${HOSTNAME}"},
                ],
                "healthCheck": {
                    "command": ["CMD-SHELL", "python -c \"import taskiq; print('healthy')\""],
                    "interval": 30,
                    "timeout": 5,
                    "retries": 3,
                    "startPeriod": 60,
                },
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/aws/ecs/taskiq-worker",
                        "awslogs-region": region,
                        "awslogs-stream-prefix": "ecs",
                        "awslogs-create-group": "true",
                    },
                },
                "stopTimeout": 300,
            }
        ])
    )

    taskiq_worker = ecs.TaskDefinition(
        f"{resource_name}-worker",
        family=f"{project_name}-taskiq-worker-{environment}",
        network_mode="awsvpc",
        requires_compatibilities=["FARGATE"],
        cpu="512",
        memory="1024",
        execution_role_arn=execution_role_arn,
        task_role_arn=task_role_arn,
        container_definitions=worker_definitions,
        opts=ResourceOptions(provider=provider),
    )

    return TaskDefinitions(
        dagster_daemon=dagster_daemon,
        dagster_webserver=dagster_webserver,
        taskiq_worker=taskiq_worker,
    )
