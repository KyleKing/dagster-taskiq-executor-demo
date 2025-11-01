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

# Dead Letter Queue for failed messages
dlq = aws.sqs.Queue(
    "taskiq-dlq",
    name=f"{project_name}-taskiq-dlq-{environment}.fifo",
    fifo_queue=True,
    content_based_deduplication=True,
    deduplication_scope="messageGroup",
    fifo_throughput_limit="perMessageGroupId",
    visibility_timeout_seconds=60,  # Shorter timeout for DLQ
    message_retention_seconds=1209600,  # 14 days retention
    opts=ResourceOptions(provider=provider),
)

# SQS FIFO Queue for TaskIQ with enhanced configuration
taskiq_queue = aws.sqs.Queue(
    "taskiq-queue",
    name=f"{project_name}-taskiq-{environment}.fifo",
    fifo_queue=True,
    content_based_deduplication=True,
    deduplication_scope="messageGroup",
    fifo_throughput_limit="perMessageGroupId",
    visibility_timeout_seconds=900,  # 15 minutes for long-running ops
    message_retention_seconds=1209600,  # 14 days retention
    max_message_size=262144,  # 256KB max message size
    delay_seconds=0,  # No delivery delay
    receive_wait_time_seconds=20,  # Long polling for efficiency
    # Configure redrive policy for failed message handling
    redrive_policy=pulumi.Output.all(dlq.arn).apply(
        lambda dlq_arn: f'{{"deadLetterTargetArn":"{dlq_arn[0]}","maxReceiveCount":3}}'
    ),
    opts=ResourceOptions(provider=provider),
)

# SQS Queue Policy for TaskIQ queue
taskiq_queue_policy = aws.sqs.QueuePolicy(
    "taskiq-queue-policy",
    queue_url=taskiq_queue.id,
    policy=pulumi.Output.all(taskiq_queue.arn, ecs_task_role.arn).apply(
        lambda args: f"""{{
            "Version": "2012-10-17",
            "Statement": [
                {{
                    "Sid": "AllowTaskIQAccess",
                    "Effect": "Allow",
                    "Principal": {{
                        "AWS": "{args[1]}"
                    }},
                    "Action": [
                        "sqs:SendMessage",
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes",
                        "sqs:ChangeMessageVisibility"
                    ],
                    "Resource": "{args[0]}"
                }}
            ]
        }}"""
    ),
    opts=ResourceOptions(provider=provider),
)

# SQS Queue Policy for Dead Letter Queue
dlq_policy = aws.sqs.QueuePolicy(
    "taskiq-dlq-policy",
    queue_url=dlq.id,
    policy=pulumi.Output.all(dlq.arn, ecs_task_role.arn).apply(
        lambda args: f"""{{
            "Version": "2012-10-17",
            "Statement": [
                {{
                    "Sid": "AllowDLQAccess",
                    "Effect": "Allow",
                    "Principal": {{
                        "AWS": "{args[1]}"
                    }},
                    "Action": [
                        "sqs:SendMessage",
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes"
                    ],
                    "Resource": "{args[0]}"
                }}
            ]
        }}"""
    ),
    opts=ResourceOptions(provider=provider),
)

# RDS Subnet Group
rds_subnet_group = aws.rds.SubnetGroup(
    "dagster-rds-subnet-group",
    name=f"{project_name}-rds-{environment}",
    subnet_ids=default_subnets.ids,
    description="Subnet group for Dagster RDS instance",
    opts=ResourceOptions(provider=provider),
)

# RDS PostgreSQL Instance for Dagster storage
rds_instance = aws.rds.Instance(
    "dagster-rds",
    identifier=f"{project_name}-rds-{environment}",
    engine="postgres",
    engine_version="15.4",
    instance_class="db.t3.micro",
    allocated_storage=20,
    max_allocated_storage=100,  # Enable storage autoscaling
    storage_type="gp2",
    storage_encrypted=False,  # LocalStack doesn't support encryption
    db_name="dagster",
    username="dagster",
    password="dagster",
    vpc_security_group_ids=[dagster_sg.id],
    db_subnet_group_name=rds_subnet_group.name,
    skip_final_snapshot=True,
    publicly_accessible=True,
    backup_retention_period=7,  # 7 days backup retention
    backup_window="03:00-04:00",  # UTC backup window
    maintenance_window="sun:04:00-sun:05:00",  # UTC maintenance window
    auto_minor_version_upgrade=True,
    multi_az=False,  # Single AZ for LocalStack
    monitoring_interval=0,  # Disable enhanced monitoring for LocalStack
    performance_insights_enabled=False,  # Not supported in LocalStack
    deletion_protection=False,  # Allow deletion for dev environment
    # Database parameters optimized for Dagster workloads
    parameter_group_name="default.postgres15",
    opts=ResourceOptions(provider=provider),
)

# ECS Cluster with enhanced configuration
ecs_cluster = aws.ecs.Cluster(
    "dagster-cluster",
    name=f"{project_name}-{environment}",
    settings=[
        aws.ecs.ClusterSettingArgs(
            name="containerInsights",
            value="enabled",
        )
    ],
    configuration=aws.ecs.ClusterConfigurationArgs(
        execute_command_configuration=aws.ecs.ClusterConfigurationExecuteCommandConfigurationArgs(
            logging="DEFAULT",
        )
    ),
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

# ECS Task Execution Role
ecs_execution_role = aws.iam.Role(
    "ecs-execution-role",
    name=f"{project_name}-ecs-execution-{environment}",
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

# Attach execution role policy
execution_role_policy = aws.iam.RolePolicyAttachment(
    "ecs-execution-role-policy",
    role=ecs_execution_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
    opts=ResourceOptions(provider=provider),
)

# IAM Policy for TaskIQ workers - SQS access
taskiq_worker_policy = aws.iam.RolePolicy(
    "taskiq-worker-policy",
    role=ecs_task_role.id,
    policy=pulumi.Output.all(taskiq_queue.arn, dlq.arn).apply(
        lambda arns: f"""{{
            "Version": "2012-10-17",
            "Statement": [
                {{
                    "Sid": "SQSTaskIQAccess",
                    "Effect": "Allow",
                    "Action": [
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:SendMessage",
                        "sqs:GetQueueAttributes",
                        "sqs:GetQueueUrl",
                        "sqs:ChangeMessageVisibility",
                        "sqs:ChangeMessageVisibilityBatch"
                    ],
                    "Resource": [
                        "{arns[0]}",
                        "{arns[1]}"
                    ]
                }},
                {{
                    "Sid": "SQSListQueues",
                    "Effect": "Allow",
                    "Action": [
                        "sqs:ListQueues"
                    ],
                    "Resource": "*"
                }},
                {{
                    "Sid": "RDSAccess",
                    "Effect": "Allow",
                    "Action": [
                        "rds:DescribeDBInstances",
                        "rds:Connect"
                    ],
                    "Resource": "*"
                }},
                {{
                    "Sid": "CloudWatchLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams"
                    ],
                    "Resource": "*"
                }},
                {{
                    "Sid": "ECSAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecs:DescribeServices",
                        "ecs:UpdateService",
                        "ecs:DescribeTasks",
                        "ecs:ListTasks",
                        "ecs:DescribeClusters"
                    ],
                    "Resource": "*"
                }}
            ]
        }}"""
    ),
    opts=ResourceOptions(provider=provider),
)

# Separate IAM policy for Dagster daemon with additional permissions
dagster_daemon_policy = aws.iam.RolePolicy(
    "dagster-daemon-policy",
    role=ecs_task_role.id,
    policy=pulumi.Output.all(taskiq_queue.arn, dlq.arn).apply(
        lambda arns: f"""{{
            "Version": "2012-10-17",
            "Statement": [
                {{
                    "Sid": "SQSFullAccess",
                    "Effect": "Allow",
                    "Action": [
                        "sqs:*"
                    ],
                    "Resource": [
                        "{arns[0]}",
                        "{arns[1]}"
                    ]
                }},
                {{
                    "Sid": "SQSListQueues",
                    "Effect": "Allow",
                    "Action": [
                        "sqs:ListQueues"
                    ],
                    "Resource": "*"
                }},
                {{
                    "Sid": "RDSFullAccess",
                    "Effect": "Allow",
                    "Action": [
                        "rds:*"
                    ],
                    "Resource": "*"
                }},
                {{
                    "Sid": "ECSFullAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecs:*"
                    ],
                    "Resource": "*"
                }},
                {{
                    "Sid": "CloudWatchLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:*"
                    ],
                    "Resource": "*"
                }}
            ]
        }}"""
    ),
    opts=ResourceOptions(provider=provider),
)

# ECS Task Definition for Dagster Daemon
dagster_daemon_task = aws.ecs.TaskDefinition(
    "dagster-daemon-task",
    family=f"{project_name}-dagster-daemon-{environment}",
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    cpu="512",
    memory="1024",
    execution_role_arn=ecs_execution_role.arn,
    task_role_arn=ecs_task_role.arn,
    container_definitions=pulumi.Output.all(rds_instance.endpoint, taskiq_queue.id, ecs_cluster.name).apply(
        lambda args: f"""[
            {{
                "name": "dagster-daemon",
                "image": "dagster-taskiq:latest",
                "essential": true,
                "environment": [
                    {{"name": "POSTGRES_HOST", "value": "{args[0].split(':')[0]}"}},
                    {{"name": "POSTGRES_PORT", "value": "5432"}},
                    {{"name": "POSTGRES_USER", "value": "dagster"}},
                    {{"name": "POSTGRES_PASSWORD", "value": "dagster"}},
                    {{"name": "POSTGRES_DB", "value": "dagster"}},
                    {{"name": "AWS_ENDPOINT_URL", "value": "http://localstack:4566"}},
                    {{"name": "AWS_DEFAULT_REGION", "value": "{region}"}},
                    {{"name": "TASKIQ_QUEUE_NAME", "value": "{args[1]}"}},
                    {{"name": "ECS_CLUSTER_NAME", "value": "{args[2]}"}},
                    {{"name": "DAGSTER_HOME", "value": "/opt/dagster/dagster_home"}},
                    {{"name": "PYTHONPATH", "value": "/opt/dagster/app"}}
                ],
                "healthCheck": {{
                    "command": ["CMD-SHELL", "python -c \\"import dagster; print('healthy')\\""],
                    "interval": 30,
                    "timeout": 5,
                    "retries": 3,
                    "startPeriod": 60
                }},
                "logConfiguration": {{
                    "logDriver": "awslogs",
                    "options": {{
                        "awslogs-group": "/aws/ecs/dagster-daemon",
                        "awslogs-region": "{region}",
                        "awslogs-stream-prefix": "ecs",
                        "awslogs-create-group": "true"
                    }}
                }},
                "stopTimeout": 120
            }}
        ]"""
    ),
    opts=ResourceOptions(provider=provider),
)

# ECS Task Definition for Dagster Webserver
dagster_webserver_task = aws.ecs.TaskDefinition(
    "dagster-webserver-task",
    family=f"{project_name}-dagster-webserver-{environment}",
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    cpu="512",
    memory="1024",
    execution_role_arn=ecs_execution_role.arn,
    task_role_arn=ecs_task_role.arn,
    container_definitions=pulumi.Output.all(rds_instance.endpoint).apply(
        lambda args: f"""[
            {{
                "name": "dagster-webserver",
                "image": "dagster-taskiq:latest",
                "essential": true,
                "portMappings": [
                    {{
                        "containerPort": 3000,
                        "protocol": "tcp",
                        "name": "dagster-web"
                    }}
                ],
                "environment": [
                    {{"name": "POSTGRES_HOST", "value": "{args[0].split(':')[0]}"}},
                    {{"name": "POSTGRES_PORT", "value": "5432"}},
                    {{"name": "POSTGRES_USER", "value": "dagster"}},
                    {{"name": "POSTGRES_PASSWORD", "value": "dagster"}},
                    {{"name": "POSTGRES_DB", "value": "dagster"}},
                    {{"name": "AWS_ENDPOINT_URL", "value": "http://localstack:4566"}},
                    {{"name": "AWS_DEFAULT_REGION", "value": "{region}"}},
                    {{"name": "DAGSTER_HOME", "value": "/opt/dagster/dagster_home"}},
                    {{"name": "PYTHONPATH", "value": "/opt/dagster/app"}}
                ],
                "healthCheck": {{
                    "command": ["CMD-SHELL", "curl -f http://localhost:3000/server_info || exit 1"],
                    "interval": 30,
                    "timeout": 5,
                    "retries": 3,
                    "startPeriod": 60
                }},
                "logConfiguration": {{
                    "logDriver": "awslogs",
                    "options": {{
                        "awslogs-group": "/aws/ecs/dagster-webserver",
                        "awslogs-region": "{region}",
                        "awslogs-stream-prefix": "ecs",
                        "awslogs-create-group": "true"
                    }}
                }},
                "stopTimeout": 30
            }}
        ]"""
    ),
    opts=ResourceOptions(provider=provider),
)

# ECS Task Definition for TaskIQ Worker
taskiq_worker_task = aws.ecs.TaskDefinition(
    "taskiq-worker-task",
    family=f"{project_name}-taskiq-worker-{environment}",
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    cpu="512",  # Increased CPU for better performance
    memory="1024",  # Increased memory for Dagster ops
    execution_role_arn=ecs_execution_role.arn,
    task_role_arn=ecs_task_role.arn,
    container_definitions=pulumi.Output.all(rds_instance.endpoint, taskiq_queue.id, dlq.id).apply(
        lambda args: f"""[
            {{
                "name": "taskiq-worker",
                "image": "dagster-taskiq:latest",
                "essential": true,
                "environment": [
                    {{"name": "POSTGRES_HOST", "value": "{args[0].split(':')[0]}"}},
                    {{"name": "POSTGRES_PORT", "value": "5432"}},
                    {{"name": "POSTGRES_USER", "value": "dagster"}},
                    {{"name": "POSTGRES_PASSWORD", "value": "dagster"}},
                    {{"name": "POSTGRES_DB", "value": "dagster"}},
                    {{"name": "AWS_ENDPOINT_URL", "value": "http://localstack:4566"}},
                    {{"name": "AWS_DEFAULT_REGION", "value": "{region}"}},
                    {{"name": "TASKIQ_QUEUE_NAME", "value": "{args[1]}"}},
                    {{"name": "TASKIQ_DLQ_NAME", "value": "{args[2]}"}},
                    {{"name": "DAGSTER_HOME", "value": "/opt/dagster/dagster_home"}},
                    {{"name": "PYTHONPATH", "value": "/opt/dagster/app"}},
                    {{"name": "WORKER_CONCURRENCY", "value": "2"}},
                    {{"name": "TASKIQ_WORKER_ID", "value": "worker-${{HOSTNAME}}"}}
                ],
                "healthCheck": {{
                    "command": ["CMD-SHELL", "python -c \\"import taskiq; print('healthy')\\""],
                    "interval": 30,
                    "timeout": 5,
                    "retries": 3,
                    "startPeriod": 60
                }},
                "logConfiguration": {{
                    "logDriver": "awslogs",
                    "options": {{
                        "awslogs-group": "/aws/ecs/taskiq-worker",
                        "awslogs-region": "{region}",
                        "awslogs-stream-prefix": "ecs",
                        "awslogs-create-group": "true"
                    }}
                }},
                "stopTimeout": 300
            }}
        ]"""
    ),
    opts=ResourceOptions(provider=provider),
)

# Service Discovery Namespace
service_discovery_namespace = aws.servicediscovery.PrivateDnsNamespace(
    "dagster-namespace",
    name=f"{project_name}-{environment}.local",
    vpc=default_vpc.id,
    description="Service discovery namespace for Dagster services",
    opts=ResourceOptions(provider=provider),
)

# Service Discovery Service for Dagster Webserver
dagster_webserver_discovery = aws.servicediscovery.Service(
    "dagster-webserver-discovery",
    name="dagster-webserver",
    namespace_id=service_discovery_namespace.id,
    dns_config=aws.servicediscovery.ServiceDnsConfigArgs(
        namespace_id=service_discovery_namespace.id,
        dns_records=[
            aws.servicediscovery.ServiceDnsConfigDnsRecordArgs(
                ttl=10,
                type="A",
            )
        ],
        routing_policy="MULTIVALUE",
    ),
    health_check_grace_period_seconds=10,
    opts=ResourceOptions(provider=provider),
)

# Application Load Balancer for Dagster Web UI
dagster_alb = aws.lb.LoadBalancer(
    "dagster-alb",
    name=f"{project_name}-alb-{environment}",
    load_balancer_type="application",
    subnets=default_subnets.ids,
    security_groups=[dagster_sg.id],
    internal=False,
    opts=ResourceOptions(provider=provider),
)

# Target Group for Dagster Web UI
dagster_target_group = aws.lb.TargetGroup(
    "dagster-target-group",
    name=f"{project_name}-tg-{environment}",
    port=3000,
    protocol="HTTP",
    vpc_id=default_vpc.id,
    target_type="ip",
    health_check=aws.lb.TargetGroupHealthCheckArgs(
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

# ALB Listener
dagster_alb_listener = aws.lb.Listener(
    "dagster-alb-listener",
    load_balancer_arn=dagster_alb.arn,
    port="80",
    protocol="HTTP",
    default_actions=[
        aws.lb.ListenerDefaultActionArgs(
            type="forward",
            target_group_arn=dagster_target_group.arn,
        )
    ],
    opts=ResourceOptions(provider=provider),
)

# ECS Service for Dagster Daemon
dagster_daemon_service = aws.ecs.Service(
    "dagster-daemon-service",
    name=f"{project_name}-daemon-{environment}",
    cluster=ecs_cluster.id,
    task_definition=dagster_daemon_task.arn,
    desired_count=1,
    launch_type="FARGATE",
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=default_subnets.ids,
        security_groups=[dagster_sg.id],
        assign_public_ip=True,
    ),
    service_registries=[
        aws.ecs.ServiceServiceRegistriesArgs(
            registry_arn=service_discovery_namespace.arn,
        )
    ],
    deployment_configuration=aws.ecs.ServiceDeploymentConfigurationArgs(
        maximum_percent=200,
        minimum_healthy_percent=50,
    ),
    opts=ResourceOptions(provider=provider),
)

# ECS Service for Dagster Webserver
dagster_webserver_service = aws.ecs.Service(
    "dagster-webserver-service",
    name=f"{project_name}-webserver-{environment}",
    cluster=ecs_cluster.id,
    task_definition=dagster_webserver_task.arn,
    desired_count=1,
    launch_type="FARGATE",
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=default_subnets.ids,
        security_groups=[dagster_sg.id],
        assign_public_ip=True,
    ),
    load_balancers=[
        aws.ecs.ServiceLoadBalancerArgs(
            target_group_arn=dagster_target_group.arn,
            container_name="dagster-webserver",
            container_port=3000,
        )
    ],
    service_registries=[
        aws.ecs.ServiceServiceRegistriesArgs(
            registry_arn=dagster_webserver_discovery.arn,
        )
    ],
    deployment_configuration=aws.ecs.ServiceDeploymentConfigurationArgs(
        maximum_percent=200,
        minimum_healthy_percent=50,
    ),
    opts=ResourceOptions(provider=provider, depends_on=[dagster_alb_listener]),
)

# ECS Service for TaskIQ Workers (scalable)
taskiq_worker_service = aws.ecs.Service(
    "taskiq-worker-service",
    name=f"{project_name}-workers-{environment}",
    cluster=ecs_cluster.id,
    task_definition=taskiq_worker_task.arn,
    desired_count=2,  # Start with 2 workers
    launch_type="FARGATE",
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=default_subnets.ids,
        security_groups=[dagster_sg.id],
        assign_public_ip=True,
    ),
    deployment_configuration=aws.ecs.ServiceDeploymentConfigurationArgs(
        maximum_percent=200,
        minimum_healthy_percent=50,
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
pulumi.export("rds_endpoint", rds_instance.endpoint)
pulumi.export("rds_port", rds_instance.port)
pulumi.export("rds_db_name", rds_instance.db_name)
pulumi.export("alb_dns_name", dagster_alb.dns_name)
pulumi.export("alb_zone_id", dagster_alb.zone_id)
pulumi.export("service_discovery_namespace", service_discovery_namespace.name)
pulumi.export("dagster_daemon_service_name", dagster_daemon_service.name)
pulumi.export("dagster_webserver_service_name", dagster_webserver_service.name)
pulumi.export("taskiq_worker_service_name", taskiq_worker_service.name)
pulumi.export("dagster_web_url", pulumi.Output.concat("http://", dagster_alb.dns_name))
