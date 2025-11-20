"""TaskIQ module - bundles all TaskIQ-related infrastructure."""

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
from components.sqs_fifo import QueueResources, attach_queue_access_policy, create_fifo_queue_with_dlq


@dataclass
class TaskIQResources:
    """All TaskIQ infrastructure resources."""

    queues: QueueResources
    task_role: iam.Role
    worker_task_definition: ecs.TaskDefinition
    worker_log_group: pulumi.Resource


def create_taskiq_infrastructure(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
    region: str,
    container_image: pulumi.Input[str],
    aws_endpoint_url: str,
    database_endpoint: pulumi.Input[str],
    execution_role_arn: pulumi.Input[str],
    message_retention_seconds: int = 1209600,
    queue_visibility_timeout: int = 300,
    dlq_visibility_timeout: int = 300,
    redrive_max_receive_count: int = 3,
) -> TaskIQResources:
    """Create complete TaskIQ infrastructure including queues, IAM, and task definitions.

    Args:
        resource_name: Base name for resources
        provider: AWS provider
        project_name: Project name for naming resources
        environment: Environment name (local, dev, prod)
        region: AWS region
        container_image: Docker image for worker
        aws_endpoint_url: AWS endpoint URL (for LocalStack)
        database_endpoint: PostgreSQL database endpoint
        execution_role_arn: ECS execution role ARN
        message_retention_seconds: SQS message retention (default: 14 days)
        queue_visibility_timeout: Main queue visibility timeout
        dlq_visibility_timeout: DLQ visibility timeout
        redrive_max_receive_count: Max receives before moving to DLQ

    Returns:
        TaskIQResources: Bundle of all created resources
    """
    # Create SQS queues
    queues = create_fifo_queue_with_dlq(
        f"{resource_name}-queue",
        provider=provider,
        queue_name=f"{project_name}-taskiq-{environment}.fifo",
        dlq_name=f"{project_name}-taskiq-dlq-{environment}.fifo",
        message_retention_seconds=message_retention_seconds,
        queue_visibility_timeout=queue_visibility_timeout,
        dlq_visibility_timeout=dlq_visibility_timeout,
        redrive_max_receive_count=redrive_max_receive_count,
    )

    # Create IAM role for TaskIQ workers
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
        name=f"{project_name}-taskiq-task-{environment}",
        assume_role_policy=assume_role_policy,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Attach TaskIQ-specific IAM permissions
    inline_policy = pulumi.Output.all(queues.queue.arn, queues.dead_letter_queue.arn).apply(
        lambda arns: json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "SQSTaskIQAccess",
                    "Effect": "Allow",
                    "Action": [
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:SendMessage",
                        "sqs:GetQueueAttributes",
                        "sqs:GetQueueUrl",
                        "sqs:ChangeMessageVisibility",
                        "sqs:ChangeMessageVisibilityBatch",
                        "sqs:ListQueues",
                        "sqs:ListQueueTags",
                    ],
                    "Resource": [arns[0], arns[1]],
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

    # Create CloudWatch log group for workers
    worker_log_group = create_ecs_log_group(
        f"{resource_name}-worker-logs",
        provider=provider,
        log_group_name=f"/aws/ecs/taskiq-worker-{environment}",
        retention_in_days=14,
    )

    # Attach queue access policy
    attach_queue_access_policy(
        f"{resource_name}-queue-access",
        provider=provider,
        queues=queues,
        principal_arns=pulumi.Output.from_input(task_role.arn).apply(lambda arn: [arn]),
        actions=[
            "sqs:SendMessage",
            "sqs:ReceiveMessage",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes",
            "sqs:ChangeMessageVisibility",
        ],
    )

    # Create worker task definition
    def create_worker_container(args: tuple[str, str, str, str]) -> list[ContainerDefinition]:
        db_endpoint, queue_name, dlq_name, image = args
        host = db_endpoint.split(":", maxsplit=1)[0]

        return [
            ContainerDefinition(
                name="taskiq-worker",
                image=image,
                command=["python", "-m", "dagster_taskiq.taskiq_executor.worker"],
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
                    "TASKIQ_DLQ_NAME": dlq_name,
                    "TASKIQ_WORKER_CONCURRENCY": "4",
                    "TASKIQ_WORKER_HEALTH_PORT": "8080",
                    "TASKIQ_WORKER_ID": "worker-${HOSTNAME}",
                },
                health_check=HealthCheck(
                    command=["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
                    interval=30,
                    timeout=10,
                    retries=2,
                    start_period=90,
                ),
                log_config=LogConfig(log_group=f"/aws/ecs/taskiq-worker-{environment}", region=region),
                stop_timeout=300,
            )
        ]

    def _serialize_worker_containers(args: tuple[str, str, str, str]) -> str:
        return json.dumps([c.to_dict() for c in create_worker_container(args)])

    # Extract queue names from the queue names passed to create_fifo_queue_with_dlq
    queue_name = f"{project_name}-taskiq-{environment}.fifo"
    dlq_name = f"{project_name}-taskiq-dlq-{environment}.fifo"

    container_defs_json = pulumi.Output.all(database_endpoint, queue_name, dlq_name, container_image).apply(
        lambda args: _serialize_worker_containers(cast("tuple[str, str, str, str]", tuple(args)))
    )

    worker_task_definition = create_fargate_task_definition(
        f"{resource_name}-worker-task",
        provider=provider,
        family=f"{project_name}-taskiq-worker-{environment}",
        container_definitions=container_defs_json,
        execution_role_arn=execution_role_arn,
        task_role_arn=task_role.arn,
        cpu="512",
        memory="1024",
    )

    return TaskIQResources(
        queues=queues,
        task_role=task_role,
        worker_task_definition=worker_task_definition,
        worker_log_group=worker_log_group,
    )
