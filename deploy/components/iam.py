"""IAM roles and policies for the ECS services."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pulumi
from pulumi import ResourceOptions
from pulumi_aws import Provider, iam


@dataclass
class IamRoles:
    """Outputs for the ECS task and execution roles."""

    task_role: iam.Role
    execution_role: iam.Role


def create_ecs_iam_roles(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
    queue_arn: pulumi.Input[str],
    dlq_arn: pulumi.Input[str],
) -> IamRoles:
    """Create IAM roles used by the Dagster ECS services.

    Returns:
        IamRoles: Wrapper containing the task and execution roles.
    """
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
        f"{resource_name}-task",
        name=f"{project_name}-ecs-task-{environment}",
        assume_role_policy=assume_role_policy,
        opts=ResourceOptions(provider=provider),
    )

    execution_role = iam.Role(
        f"{resource_name}-execution",
        name=f"{project_name}-ecs-execution-{environment}",
        assume_role_policy=assume_role_policy,
        opts=ResourceOptions(provider=provider),
    )

    iam.RolePolicyAttachment(
        f"{resource_name}-execution-policy",
        role=execution_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
        opts=ResourceOptions(provider=provider),
    )

    inline_policy = pulumi.Output.all(queue_arn, dlq_arn).apply(
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
        })
    )

    iam.RolePolicy(
        f"{resource_name}-inline",
        role=task_role.id,
        policy=inline_policy,
        opts=ResourceOptions(provider=provider),
    )

    return IamRoles(task_role=task_role, execution_role=execution_role)
