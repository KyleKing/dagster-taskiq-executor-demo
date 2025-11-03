"""TaskIQ demo module - provisions API and worker services with SQS."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Sequence

import pulumi
from pulumi_aws import Provider, ec2, ecs, iam, sqs

from components.cloudwatch_logs import create_ecs_log_group
from components.ecs_helpers import (
    ContainerDefinition,
    HealthCheck,
    LogConfig,
    PortMapping,
    create_fargate_task_definition,
)


@dataclass
class TaskiqDemoResources:
    """Bundle of resources created for the TaskIQ demo."""

    queue: sqs.Queue
    task_role: iam.Role
    security_group: ec2.SecurityGroup
    api_log_group: pulumi.Resource
    worker_log_group: pulumi.Resource
    api_task_definition: ecs.TaskDefinition
    worker_task_definition: ecs.TaskDefinition
    api_service: ecs.Service
    worker_service: ecs.Service


def create_taskiq_demo_infrastructure(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
    region: str,
    cluster_arn: pulumi.Input[str],
    vpc_id: pulumi.Input[str],
    subnet_ids: pulumi.Input[Sequence[str]],
    container_image: pulumi.Input[str],
    aws_endpoint_url: str,
    aws_access_key: str,
    aws_secret_key: str,
    queue_name: str,
    message_retention_seconds: int,
    visibility_timeout: int,
    execution_role_arn: pulumi.Input[str],
    api_desired_count: int,
    worker_desired_count: int,
    assign_public_ip: bool = True,
) -> TaskiqDemoResources:
    """Provision SQS queue plus API/worker ECS services for the TaskIQ demo."""

    queue = sqs.Queue(
        f"{resource_name}-queue",
        name=queue_name,
        visibility_timeout_seconds=visibility_timeout,
        message_retention_seconds=message_retention_seconds,
        opts=pulumi.ResourceOptions(provider=provider),
    )

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
        name=f"{project_name}-taskiq-demo-task-{environment}",
        assume_role_policy=assume_role_policy,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    iam.RolePolicy(
        f"{resource_name}-inline-policy",
        role=task_role.id,
        policy=queue.arn.apply(
            lambda arn: json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "TaskQueueAccess",
                        "Effect": "Allow",
                        "Action": [
                            "sqs:ReceiveMessage",
                            "sqs:DeleteMessage",
                            "sqs:SendMessage",
                            "sqs:GetQueueAttributes",
                            "sqs:GetQueueUrl",
                            "sqs:ChangeMessageVisibility",
                        ],
                        "Resource": [arn],
                    },
                    {
                        "Sid": "AllowLogs",
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
        ),
        opts=pulumi.ResourceOptions(provider=provider),
    )

    security_group = ec2.SecurityGroup(
        f"{resource_name}-sg",
        name=f"{project_name}-taskiq-demo-{environment}",
        description="Security group for TaskIQ demo services",
        vpc_id=vpc_id,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Allow inbound traffic for API health and requests
    ec2.SecurityGroupRule(
        f"{resource_name}-api-ingress",
        type="ingress",
        security_group_id=security_group.id,
        from_port=8000,
        to_port=8000,
        protocol="tcp",
        cidr_blocks=["0.0.0.0/0"],
        description="TaskIQ demo API access",
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

    api_log_group_name = f"/aws/ecs/taskiq-demo-api-{environment}"
    worker_log_group_name = f"/aws/ecs/taskiq-demo-worker-{environment}"

    api_log_group = create_ecs_log_group(
        f"{resource_name}-api-logs",
        provider=provider,
        log_group_name=api_log_group_name,
        retention_in_days=7,
    )

    worker_log_group = create_ecs_log_group(
        f"{resource_name}-worker-logs",
        provider=provider,
        log_group_name=worker_log_group_name,
        retention_in_days=7,
    )

    def _base_environment(role: str) -> dict[str, str]:
        return {
            "SERVICE_ROLE": role,
            "TASKIQ_DEMO_SQS_QUEUE_NAME": queue_name,
            "TASKIQ_DEMO_SQS_ENDPOINT_URL": aws_endpoint_url,
            "TASKIQ_DEMO_AWS_ACCESS_KEY_ID": aws_access_key,
            "TASKIQ_DEMO_AWS_SECRET_ACCESS_KEY": aws_secret_key,
            "TASKIQ_DEMO_AWS_REGION": region,
            "TASKIQ_DEMO_LOG_LEVEL": "INFO",
            "AWS_DEFAULT_REGION": region,
        }

    def _api_container(args: tuple[str, str]) -> str:
        image, queue_url = args
        container = ContainerDefinition(
            name="taskiq-demo-api",
            image=image,
            environment={**_base_environment("api"), "TASKIQ_DEMO_SQS_QUEUE_URL": queue_url},
            port_mappings=[PortMapping(container_port=8000)],
            health_check=HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
                interval=30,
                timeout=5,
                retries=3,
                start_period=30,
            ),
            log_config=LogConfig(
                log_group=api_log_group_name,
                region=region,
                stream_prefix="api",
            ),
            stop_timeout=30,
        )
        return json.dumps([container.to_dict()])

    def _worker_container(image: str) -> str:
        container = ContainerDefinition(
            name="taskiq-demo-worker",
            image=image,
            environment=_base_environment("worker"),
            log_config=LogConfig(
                log_group=worker_log_group_name,
                region=region,
                stream_prefix="worker",
            ),
            stop_timeout=30,
        )
        return json.dumps([container.to_dict()])

    image_output = pulumi.Output.from_input(container_image)

    api_containers = pulumi.Output.all(image_output, queue.id).apply(
        lambda args: _api_container((args[0], args[1])),
    )

    worker_containers = image_output.apply(_worker_container)

    api_task_definition = create_fargate_task_definition(
        f"{resource_name}-api-task",
        provider=provider,
        family=f"{project_name}-taskiq-demo-api-{environment}",
        container_definitions=api_containers,
        execution_role_arn=execution_role_arn,
        task_role_arn=task_role.arn,
        cpu="256",
        memory="512",
    )

    worker_task_definition = create_fargate_task_definition(
        f"{resource_name}-worker-task",
        provider=provider,
        family=f"{project_name}-taskiq-demo-worker-{environment}",
        container_definitions=worker_containers,
        execution_role_arn=execution_role_arn,
        task_role_arn=task_role.arn,
        cpu="256",
        memory="512",
    )

    security_groups = security_group.id.apply(lambda sg: [sg])

    api_service = ecs.Service(
        f"{resource_name}-api-service",
        ecs.ServiceArgs(
            name=f"{project_name}-taskiq-demo-api-{environment}",
            cluster=cluster_arn,
            task_definition=api_task_definition.arn,
            desired_count=api_desired_count,
            launch_type="FARGATE",
            network_configuration=ecs.ServiceNetworkConfigurationArgs(
                subnets=subnet_ids,
                security_groups=security_groups,
                assign_public_ip=assign_public_ip,
            ),
        ),
        opts=pulumi.ResourceOptions(provider=provider),
    )

    worker_service = ecs.Service(
        f"{resource_name}-worker-service",
        ecs.ServiceArgs(
            name=f"{project_name}-taskiq-demo-worker-{environment}",
            cluster=cluster_arn,
            task_definition=worker_task_definition.arn,
            desired_count=worker_desired_count,
            launch_type="FARGATE",
            network_configuration=ecs.ServiceNetworkConfigurationArgs(
                subnets=subnet_ids,
                security_groups=security_groups,
                assign_public_ip=assign_public_ip,
            ),
        ),
        opts=pulumi.ResourceOptions(provider=provider),
    )

    return TaskiqDemoResources(
        queue=queue,
        task_role=task_role,
        security_group=security_group,
        api_log_group=api_log_group,
        worker_log_group=worker_log_group,
        api_task_definition=api_task_definition,
        worker_task_definition=worker_task_definition,
        api_service=api_service,
        worker_service=worker_service,
    )
