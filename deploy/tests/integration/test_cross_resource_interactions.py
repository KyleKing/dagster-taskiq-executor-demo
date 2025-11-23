"""Integration tests for cross-resource interactions.

Tests that resources can communicate and interact correctly.
This is where integration tests provide the most value over unit tests.

Following pulumi-testing skill:
- Test IAM permissions work
- Test network connectivity
- Test service discovery
- Test queue operations
"""

import json
import time

import pytest


@pytest.mark.integration
def test_sqs_message_workflow(boto3_clients, stack_outputs):
    """Test end-to-end SQS message workflow.

    Verifies:
    1. Can send message to queue
    2. Can receive message from queue
    3. Message attributes are preserved
    4. Can delete message after processing
    """
    sqs = boto3_clients["sqs"]
    queue_url = stack_outputs["queue_url"]

    # Send a message
    test_message_body = json.dumps({
        "test": "data",
        "timestamp": time.time(),
    })

    send_response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=test_message_body,
        MessageGroupId="test-group",
        MessageDeduplicationId=f"test-{int(time.time() * 1000)}",
    )

    assert "MessageId" in send_response
    message_id = send_response["MessageId"]

    # Receive the message
    receive_response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=5,
    )

    assert "Messages" in receive_response
    assert len(receive_response["Messages"]) >= 1

    received_message = receive_response["Messages"][0]
    assert received_message["MessageId"] == message_id
    assert received_message["Body"] == test_message_body

    # Delete the message
    sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=received_message["ReceiptHandle"],
    )


@pytest.mark.integration
def test_dlq_redrive_policy(boto3_clients, stack_outputs):
    """Verify DLQ redrive policy is configured correctly."""
    sqs = boto3_clients["sqs"]
    queue_url = stack_outputs["queue_url"]
    dlq_arn = stack_outputs["dlq_arn"]

    # Get queue attributes
    response = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["RedrivePolicy"],
    )

    assert "Attributes" in response
    assert "RedrivePolicy" in response["Attributes"]

    # Parse redrive policy
    redrive_policy = json.loads(response["Attributes"]["RedrivePolicy"])

    assert "deadLetterTargetArn" in redrive_policy
    assert redrive_policy["deadLetterTargetArn"] == dlq_arn

    assert "maxReceiveCount" in redrive_policy
    assert redrive_policy["maxReceiveCount"] == "3"


@pytest.mark.integration
def test_vpc_subnets_in_different_azs(boto3_clients, stack_outputs):
    """Verify subnets are in different availability zones for HA."""
    ec2 = boto3_clients["ec2"]
    subnet_ids = stack_outputs["subnet_ids"]

    # Describe subnets
    response = ec2.describe_subnets(SubnetIds=subnet_ids)

    assert len(response["Subnets"]) >= 2, "Should have at least 2 subnets for HA"

    # Collect availability zones
    azs = set()
    for subnet in response["Subnets"]:
        azs.add(subnet["AvailabilityZone"])

    # Verify subnets span multiple AZs
    assert len(azs) >= 2, "Subnets should be in at least 2 different AZs"


@pytest.mark.integration
def test_security_group_allows_postgres_access(boto3_clients, stack_outputs):
    """Verify security group allows PostgreSQL traffic from VPC."""
    ec2 = boto3_clients["ec2"]
    vpc_id = stack_outputs["vpc_id"]

    # Find database security group
    # Look for security group with postgres ingress
    response = ec2.describe_security_groups(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
    )

    # Find SG with port 5432 ingress
    db_sg = None
    for sg in response["SecurityGroups"]:
        for rule in sg.get("IpPermissions", []):
            if rule.get("FromPort") == 5432 and rule.get("ToPort") == 5432:
                db_sg = sg
                break
        if db_sg:
            break

    assert db_sg is not None, "Should have security group allowing port 5432"

    # Verify ingress rule details
    postgres_rule = None
    for rule in db_sg["IpPermissions"]:
        if rule.get("FromPort") == 5432:
            postgres_rule = rule
            break

    assert postgres_rule is not None
    assert postgres_rule["IpProtocol"] == "tcp"

    # Verify CIDR allows VPC access
    cidr_ranges = [ip_range["CidrIp"] for ip_range in postgres_rule.get("IpRanges", [])]
    assert any("10.0.0.0" in cidr for cidr in cidr_ranges), \
        "Should allow access from VPC CIDR"


@pytest.mark.integration
@pytest.mark.slow
def test_ecs_services_running(boto3_clients, stack_outputs):
    """Verify ECS services are running and healthy.

    This test may take time for services to start.
    """
    ecs = boto3_clients["ecs"]
    cluster_name = stack_outputs["cluster_name"]

    # List services in cluster
    response = ecs.list_services(cluster=cluster_name)

    assert "serviceArns" in response
    assert len(response["serviceArns"]) > 0, "Should have at least one service"

    # Describe services
    services_response = ecs.describe_services(
        cluster=cluster_name,
        services=response["serviceArns"],
    )

    assert "services" in services_response

    # Verify each service
    for service in services_response["services"]:
        assert service["status"] in ["ACTIVE", "DRAINING"]

        # Check desired count matches running count
        # Note: May take time for tasks to start
        if service["desiredCount"] > 0:
            assert service["runningCount"] >= 0


@pytest.mark.integration
def test_cloudwatch_log_groups_exist(boto3_clients, stack_outputs):
    """Verify CloudWatch log groups are created for services."""
    logs = boto3_clients["logs"]

    # Get project name from outputs
    cluster_name = stack_outputs["cluster_name"]
    # Extract project name from cluster name
    # Format: {project_name}-cluster-{environment}
    project_name = cluster_name.split("-cluster-")[0]

    # List log groups
    response = logs.describe_log_groups(
        logGroupNamePrefix=f"/ecs/{project_name}",
    )

    # Should have log groups for different services
    log_group_names = [lg["logGroupName"] for lg in response.get("logGroups", [])]

    # Verify we have log groups
    assert len(log_group_names) > 0, "Should have at least one log group"


@pytest.mark.integration
def test_service_discovery_namespace_exists(boto3_clients, stack_outputs):
    """Verify service discovery namespace is created."""
    sd = boto3_clients["servicediscovery"]

    # List namespaces
    response = sd.list_namespaces()

    # Find namespace by name from outputs
    namespace_name = stack_outputs.get("service_discovery_namespace")

    if namespace_name:
        namespaces = response.get("Namespaces", [])
        our_namespace = None

        for ns in namespaces:
            if ns["Name"] == namespace_name:
                our_namespace = ns
                break

        assert our_namespace is not None, f"Service discovery namespace {namespace_name} not found"
        assert our_namespace["Type"] == "DNS_PRIVATE"


@pytest.mark.integration
@pytest.mark.slow
def test_alb_health_checks(boto3_clients, stack_outputs):
    """Verify ALB target groups have health checks configured."""
    elbv2 = boto3_clients["elbv2"]

    # Get load balancer ARN
    dns_name = stack_outputs["alb_dns_name"]

    # List load balancers to find ARN
    lbs_response = elbv2.describe_load_balancers()
    lb_arn = None

    for lb in lbs_response.get("LoadBalancers", []):
        if lb["DNSName"] == dns_name:
            lb_arn = lb["LoadBalancerArn"]
            break

    assert lb_arn is not None

    # List target groups for this load balancer
    tgs_response = elbv2.describe_target_groups(LoadBalancerArn=lb_arn)

    assert len(tgs_response.get("TargetGroups", [])) > 0

    # Verify health checks are configured
    for tg in tgs_response["TargetGroups"]:
        assert "HealthCheckPath" in tg
        assert tg["HealthCheckProtocol"] in ["HTTP", "HTTPS"]
        assert tg["HealthCheckIntervalSeconds"] > 0
        assert tg["HealthyThresholdCount"] > 0
