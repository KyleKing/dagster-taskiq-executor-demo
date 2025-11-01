"""Pulumi infrastructure for Dagster TaskIQ LocalStack demo.
Creates SQS queues, ECS cluster, RDS instance, and IAM roles.
"""

import pulumi
import pulumi_aws as aws
from pulumi import ResourceOptions

# Configuration
config = pulumi.Config()
region = config.get("region") or "us-east-1"
endpoint = config.get("endpoint") or "http://localhost:4566"
access_key = config.get("accessKey") or "test"
secret_key = config.get("secretKey") or "test"

# Project configuration
project_name = "dagster-taskiq-demo"
environment = config.get("environment") or "dev"

# Configure the AWS provider for LocalStack
provider = aws.Provider(
    "localstack",
    region=region,
    access_key=access_key,
    secret_key=secret_key,
    endpoints=[
        aws.ProviderEndpointArgs(service="ecs", url=endpoint),
        aws.ProviderEndpointArgs(service="sqs", url=endpoint),
        aws.ProviderEndpointArgs(service="rds", url=endpoint),
        aws.ProviderEndpointArgs(service="ec2", url=endpoint),
        aws.ProviderEndpointArgs(service="iam", url=endpoint),
        aws.ProviderEndpointArgs(service="sts", url=endpoint),
        aws.ProviderEndpointArgs(service="logs", url=endpoint),
    ],
    skip_credentials_validation=True,
    skip_metadata_api_check=True,
    skip_region_validation=True,
    skip_requesting_account_id=True,
    s3_force_path_style=True,
)

# VPC and Networking (using default VPC for LocalStack)
default_vpc = aws.ec2.get_vpc(default=True, opts=pulumi.InvokeOptions(provider=provider))
default_subnets = aws.ec2.get_subnets(
    filters=[aws.ec2.GetSubnetsFilterArgs(name="vpc-id", values=[default_vpc.id])],
    opts=pulumi.InvokeOptions(provider=provider),
)

# Security Groups
dagster_sg = aws.ec2.SecurityGroup(
    "dagster-sg",
    name=f"{project_name}-dagster-{environment}",
    description="Security group for Dagster services",
    vpc_id=default_vpc.id,
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            from_port=3000, to_port=3000, protocol="tcp", cidr_blocks=["0.0.0.0/0"], description="Dagster Web UI"
        ),
        aws.ec2.SecurityGroupIngressArgs(
            from_port=5432, to_port=5432, protocol="tcp", cidr_blocks=["10.0.0.0/8"], description="PostgreSQL"
        ),
    ],
    egress=[aws.ec2.SecurityGroupEgressArgs(from_port=0, to_port=0, protocol="-1", cidr_blocks=["0.0.0.0/0"])],
    opts=ResourceOptions(provider=provider),
)

# SQS FIFO Queue for TaskIQ
taskiq_queue = aws.sqs.Queue(
    "taskiq-queue",
    name=f"{project_name}-taskiq-{environment}.fifo",
    fifo_queue=True,
    content_based_deduplication=True,
    deduplication_scope="messageGroup",
    fifo_throughput_limit="perMessageGroupId",
    visibility_timeout_seconds=300,
    message_retention_seconds=1209600,  # 14 days
    opts=ResourceOptions(provider=provider),
)

# Dead Letter Queue
dlq = aws.sqs.Queue(
    "taskiq-dlq",
    name=f"{project_name}-taskiq-dlq-{environment}.fifo",
    fifo_queue=True,
    content_based_deduplication=True,
    opts=ResourceOptions(provider=provider),
)

# ECS Cluster
ecs_cluster = aws.ecs.Cluster(
    "dagster-cluster",
    name=f"{project_name}-{environment}",
    opts=ResourceOptions(provider=provider),
)

# IAM Role for ECS Tasks
ecs_task_role = aws.iam.Role(
    "ecs-task-role",
    name=f"{project_name}-ecs-task-{environment}",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": "ecs-tasks.amazonaws.com"
                }
            }
        ]
    }""",
    opts=ResourceOptions(provider=provider),
)

# IAM Policy for SQS and RDS access
task_policy = aws.iam.RolePolicy(
    "ecs-task-policy",
    role=ecs_task_role.id,
    policy=pulumi.Output.all(taskiq_queue.arn, dlq.arn).apply(
        lambda arns: f"""{{
            "Version": "2012-10-17",
            "Statement": [
                {{
                    "Effect": "Allow",
                    "Action": [
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:SendMessage",
                        "sqs:GetQueueAttributes"
                    ],
                    "Resource": [
                        "{arns[0]}",
                        "{arns[1]}"
                    ]
                }},
                {{
                    "Effect": "Allow",
                    "Action": [
                        "rds:DescribeDBInstances",
                        "rds:Connect"
                    ],
                    "Resource": "*"
                }},
                {{
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": "*"
                }}
            ]
        }}"""
    ),
    opts=ResourceOptions(provider=provider),
)

# Exports
pulumi.export("queue_url", taskiq_queue.id)
pulumi.export("queue_arn", taskiq_queue.arn)
pulumi.export("dlq_url", dlq.id)
pulumi.export("dlq_arn", dlq.arn)
pulumi.export("cluster_arn", ecs_cluster.arn)
pulumi.export("cluster_name", ecs_cluster.name)
pulumi.export("task_role_arn", ecs_task_role.arn)
pulumi.export("security_group_id", dagster_sg.id)
pulumi.export("vpc_id", default_vpc.id)
pulumi.export("subnet_ids", default_subnets.ids)
