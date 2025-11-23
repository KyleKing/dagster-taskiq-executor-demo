"""Integration tests for infrastructure deployment.

Tests that infrastructure deploys successfully and resources exist with
correct configurations.

Following pulumi-testing skill:
- Test actual resource creation (not mocked)
- Validate critical properties
- Test cross-resource interactions
"""

import pytest


@pytest.mark.integration
def test_stack_deployment_succeeds(pulumi_stack):
    """Verify stack deploys without errors."""
    assert pulumi_stack["stack"] is not None
    assert pulumi_stack["outputs"] is not None
    assert len(pulumi_stack["outputs"]) > 0


@pytest.mark.integration
def test_required_outputs_exist(stack_outputs):
    """Verify all required stack outputs are present."""
    required_outputs = [
        "queue_url",
        "queue_arn",
        "dlq_url",
        "dlq_arn",
        "cluster_arn",
        "cluster_name",
        "vpc_id",
        "subnet_ids",
        "aurora_cluster_endpoint",
        "execution_role_arn",
        "security_group_id",
        "alb_dns_name",
    ]

    for output_name in required_outputs:
        assert output_name in stack_outputs, f"Missing required output: {output_name}"
        assert stack_outputs[output_name] is not None, f"Output {output_name} is None"


@pytest.mark.integration
def test_sqs_queues_exist(boto3_clients, stack_outputs):
    """Verify SQS queues exist and have correct attributes."""
    sqs = boto3_clients["sqs"]

    # Verify main queue exists
    queue_url = stack_outputs["queue_url"]
    queue_attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["All"],
    )

    assert "Attributes" in queue_attrs
    attrs = queue_attrs["Attributes"]

    # Verify queue is FIFO
    assert queue_url.endswith(".fifo"), "Queue should be FIFO"
    assert attrs.get("FifoQueue") == "true", "Queue should have FIFO enabled"

    # Verify message retention (14 days = 1,209,600 seconds)
    assert int(attrs.get("MessageRetentionPeriod", 0)) == 1_209_600

    # Verify visibility timeout
    assert int(attrs.get("VisibilityTimeout", 0)) == 900

    # Verify DLQ exists
    dlq_url = stack_outputs["dlq_url"]
    dlq_attrs = sqs.get_queue_attributes(
        QueueUrl=dlq_url,
        AttributeNames=["All"],
    )
    assert "Attributes" in dlq_attrs
    assert dlq_url.endswith(".fifo"), "DLQ should be FIFO"


@pytest.mark.integration
def test_ecs_cluster_exists(boto3_clients, stack_outputs):
    """Verify ECS cluster exists and is active."""
    ecs = boto3_clients["ecs"]
    cluster_arn = stack_outputs["cluster_arn"]

    # Describe cluster
    response = ecs.describe_clusters(clusters=[cluster_arn])

    assert len(response["clusters"]) == 1
    cluster = response["clusters"][0]

    assert cluster["status"] == "ACTIVE"
    assert cluster["clusterArn"] == cluster_arn


@pytest.mark.integration
def test_aurora_database_exists(boto3_clients, stack_outputs):
    """Verify Aurora PostgreSQL cluster exists."""
    rds = boto3_clients["rds"]

    # List DB clusters and find ours
    response = rds.describe_db_clusters()

    # Find our cluster by endpoint
    endpoint = stack_outputs["aurora_cluster_endpoint"]
    our_cluster = None

    for cluster in response.get("DBClusters", []):
        if cluster["Endpoint"] == endpoint:
            our_cluster = cluster
            break

    assert our_cluster is not None, f"Cluster with endpoint {endpoint} not found"

    # Verify engine
    assert our_cluster["Engine"] == "aurora-postgresql"

    # Verify status
    assert our_cluster["Status"] in ["available", "creating"]


@pytest.mark.integration
def test_security_group_exists(boto3_clients, stack_outputs):
    """Verify security group exists and has correct rules."""
    ec2 = boto3_clients["ec2"]
    sg_id = stack_outputs["security_group_id"]

    # Describe security group
    response = ec2.describe_security_groups(GroupIds=[sg_id])

    assert len(response["SecurityGroups"]) == 1
    sg = response["SecurityGroups"][0]

    assert sg["GroupId"] == sg_id
    assert sg["VpcId"] == stack_outputs["vpc_id"]


@pytest.mark.integration
def test_load_balancer_exists(boto3_clients, stack_outputs):
    """Verify Application Load Balancer exists."""
    elbv2 = boto3_clients["elbv2"]

    # List load balancers
    response = elbv2.describe_load_balancers()

    # Find our ALB by DNS name
    dns_name = stack_outputs["alb_dns_name"]
    our_alb = None

    for lb in response.get("LoadBalancers", []):
        if lb["DNSName"] == dns_name:
            our_alb = lb
            break

    assert our_alb is not None, f"Load balancer with DNS {dns_name} not found"

    # Verify type
    assert our_alb["Type"] == "application"

    # Verify scheme
    assert our_alb["Scheme"] in ["internet-facing", "internal"]


@pytest.mark.integration
def test_iam_execution_role_exists(boto3_clients, stack_outputs):
    """Verify IAM execution role exists."""
    iam = boto3_clients["iam"]
    role_arn = stack_outputs["execution_role_arn"]

    # Extract role name from ARN
    # arn:aws:iam::123456789012:role/role-name
    role_name = role_arn.split("/")[-1]

    # Get role
    response = iam.get_role(RoleName=role_name)

    assert "Role" in response
    role = response["Role"]

    assert role["Arn"] == role_arn

    # Verify assume role policy allows ECS tasks
    assume_role_policy = role["AssumeRolePolicyDocument"]
    assert "Statement" in assume_role_policy

    # Check for ECS service principal
    has_ecs_principal = False
    for statement in assume_role_policy["Statement"]:
        if statement.get("Effect") == "Allow":
            principal = statement.get("Principal", {})
            service = principal.get("Service", "")
            if "ecs-tasks.amazonaws.com" in service:
                has_ecs_principal = True
                break

    assert has_ecs_principal, "Execution role should trust ecs-tasks.amazonaws.com"
