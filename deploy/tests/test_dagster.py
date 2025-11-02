"""Tests for Dagster infrastructure module."""

import json
from unittest.mock import MagicMock

import pulumi
import pulumi_aws
import pytest

from modules.dagster import DagsterResources, create_dagster_infrastructure


class Mocks(pulumi.runtime.Mocks):
    """Mock implementation for Pulumi resources."""

    def new_resource(self, args: pulumi.runtime.MockResourceArgs):
        """Mock resource creation."""
        if args.typ == "aws:ec2/securityGroup:SecurityGroup":
            return [
                f"{args.name}_id",
                {
                    **args.inputs,
                    "arn": f"arn:aws:ec2:us-east-1:123456789012:security-group/{args.name}",
                    "id": f"sg-{args.name}",
                },
            ]

        if args.typ == "aws:iam/role:Role":
            return [
                f"{args.name}_id",
                {
                    **args.inputs,
                    "arn": f"arn:aws:iam::123456789012:role/{args.name}",
                    "id": f"{args.name}_id",
                },
            ]

        if args.typ == "aws:ecs/taskDefinition:TaskDefinition":
            return [
                f"{args.name}_id",
                {
                    **args.inputs,
                    "arn": f"arn:aws:ecs:us-east-1:123456789012:task-definition/{args.name}",
                    "id": f"{args.name}_id",
                },
            ]

        if args.typ == "aws:servicediscovery/privateDnsNamespace:PrivateDnsNamespace":
            return [
                f"{args.name}_id",
                {
                    **args.inputs,
                    "arn": f"arn:aws:servicediscovery:us-east-1:123456789012:namespace/{args.name}",
                    "id": f"ns-{args.name}",
                },
            ]

        if args.typ == "aws:servicediscovery/service:Service":
            return [
                f"{args.name}_id",
                {
                    **args.inputs,
                    "arn": f"arn:aws:servicediscovery:us-east-1:123456789012:service/{args.name}",
                    "id": f"svc-{args.name}",
                },
            ]

        if args.typ == "aws:lb/loadBalancer:LoadBalancer":
            return [
                f"{args.name}_id",
                {
                    **args.inputs,
                    "arn": f"arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/{args.name}",
                    "id": f"lb-{args.name}",
                    "dns_name": f"{args.name}.us-east-1.elb.amazonaws.com",
                },
            ]

        if args.typ == "aws:lb/targetGroup:TargetGroup":
            return [
                f"{args.name}_id",
                {
                    **args.inputs,
                    "arn": f"arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/{args.name}",
                    "id": f"tg-{args.name}",
                },
            ]

        if args.typ == "aws:lb/listener:Listener":
            return [
                f"{args.name}_id",
                {
                    **args.inputs,
                    "arn": f"arn:aws:elasticloadbalancing:us-east-1:123456789012:listener/{args.name}",
                    "id": f"listener-{args.name}",
                },
            ]

        return [f"{args.name}_id", args.inputs]

    def call(self, args: pulumi.runtime.MockCallArgs):
        """Mock provider calls."""
        return {}


@pytest.fixture(autouse=True)
def setup_mocks():
    """Set up Pulumi mocks for all tests."""
    pulumi.runtime.set_mocks(Mocks())


class TestDagsterInfrastructure:
    """Test Dagster infrastructure creation."""

    def test_create_dagster_infrastructure(self):
        """Test creating Dagster infrastructure returns correct structure."""
        mock_provider = MagicMock(spec=pulumi_aws.Provider)

        result = create_dagster_infrastructure(
            resource_name="test-dagster",
            provider=mock_provider,
            project_name="dagster-taskiq-demo",
            environment="test",
            region="us-east-1",
            vpc_id="vpc-12345678",
            subnet_ids=["subnet-12345678", "subnet-87654321"],
            container_image="dagster-taskiq-demo:latest",
            aws_endpoint_url="http://localhost:4566",
            database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo",
            cluster_name="test-cluster",
            execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        )

        assert isinstance(result, DagsterResources)
        assert result.security_group is not None
        assert result.task_role is not None
        assert result.daemon_task_definition is not None
        assert result.webserver_task_definition is not None
        assert result.service_discovery_namespace is not None
        assert result.daemon_service_discovery is not None
        assert result.webserver_service_discovery is not None
        assert result.load_balancer is not None
        assert result.target_group is not None
        assert result.listener is not None

    @pulumi.runtime.test
    def test_security_group_configuration(self):
        """Test security group has correct configuration."""
        mock_provider = MagicMock(spec=pulumi_aws.Provider)
        result = create_dagster_infrastructure(
            resource_name="test-dagster",
            provider=mock_provider,
            project_name="dagster-taskiq-demo",
            environment="test",
            region="us-east-1",
            vpc_id="vpc-12345678",
            subnet_ids=["subnet-12345678", "subnet-87654321"],
            container_image="dagster-taskiq-demo:latest",
            aws_endpoint_url="http://localhost:4566",
            database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo",
            cluster_name="test-cluster",
            execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        )

        def check_security_group_properties(args):
            _urn, sg_inputs = args
            assert sg_inputs["vpc_id"] == "vpc-12345678"
            assert sg_inputs["name"] == "dagster-taskiq-demo-dagster-test"
            assert "Shared security group for Dagster services" in sg_inputs["description"]

        return pulumi.Output.all(result.security_group.urn, result.security_group.__dict__).apply(
            check_security_group_properties
        )

    @pulumi.runtime.test
    def test_task_role_configuration(self):
        """Test IAM role has correct configuration."""
        mock_provider = MagicMock(spec=pulumi_aws.Provider)
        result = create_dagster_infrastructure(
            resource_name="test-dagster",
            provider=mock_provider,
            project_name="dagster-taskiq-demo",
            environment="test",
            region="us-east-1",
            vpc_id="vpc-12345678",
            subnet_ids=["subnet-12345678", "subnet-87654321"],
            container_image="dagster-taskiq-demo:latest",
            aws_endpoint_url="http://localhost:4566",
            database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo",
            cluster_name="test-cluster",
            execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        )

        def check_task_role_properties(args):
            _urn, role_inputs = args
            assert role_inputs["name"] == "dagster-taskiq-demo-dagster-task-test"

            # Check assume role policy
            assume_policy = json.loads(role_inputs["assume_role_policy"])
            assert assume_policy["Version"] == "2012-10-17"
            assert len(assume_policy["Statement"]) == 1
            statement = assume_policy["Statement"][0]
            assert statement["Effect"] == "Allow"
            assert statement["Action"] == "sts:AssumeRole"
            assert statement["Principal"]["Service"] == "ecs-tasks.amazonaws.com"

        return pulumi.Output.all(result.task_role.urn, result.task_role.__dict__).apply(check_task_role_properties)

    @pulumi.runtime.test
    def test_daemon_task_definition_configuration(self):
        """Test daemon task definition has correct configuration."""
        mock_provider = MagicMock(spec=pulumi_aws.Provider)
        result = create_dagster_infrastructure(
            resource_name="test-dagster",
            provider=mock_provider,
            project_name="dagster-taskiq-demo",
            environment="test",
            region="us-east-1",
            vpc_id="vpc-12345678",
            subnet_ids=["subnet-12345678", "subnet-87654321"],
            container_image="dagster-taskiq-demo:latest",
            aws_endpoint_url="http://localhost:4566",
            database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo",
            cluster_name="test-cluster",
            execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        )

        def check_daemon_task_properties(args):
            _urn, task_inputs = args
            assert task_inputs["family"] == "dagster-taskiq-demo-dagster-daemon-test"
            assert task_inputs["cpu"] == "512"
            assert task_inputs["memory"] == "1024"
            assert task_inputs["execution_role_arn"] == "arn:aws:iam::123456789012:role/ecsTaskExecutionRole"

            # Check container definitions
            container_defs = json.loads(task_inputs["container_definitions"])
            assert len(container_defs) == 1
            container = container_defs[0]
            assert container["name"] == "dagster-daemon"
            assert container["image"] == "dagster-taskiq-demo:latest"
            assert container["stop_timeout"] == 120

        return pulumi.Output.all(result.daemon_task_definition.urn, result.daemon_task_definition.__dict__).apply(
            check_daemon_task_properties
        )

    @pulumi.runtime.test
    def test_webserver_task_definition_configuration(self):
        """Test webserver task definition has correct configuration."""
        mock_provider = MagicMock(spec=pulumi_aws.Provider)
        result = create_dagster_infrastructure(
            resource_name="test-dagster",
            provider=mock_provider,
            project_name="dagster-taskiq-demo",
            environment="test",
            region="us-east-1",
            vpc_id="vpc-12345678",
            subnet_ids=["subnet-12345678", "subnet-87654321"],
            container_image="dagster-taskiq-demo:latest",
            aws_endpoint_url="http://localhost:4566",
            database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo",
            cluster_name="test-cluster",
            execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        )

        def check_webserver_task_properties(args):
            _urn, task_inputs = args
            assert task_inputs["family"] == "dagster-taskiq-demo-dagster-webserver-test"
            assert task_inputs["cpu"] == "512"
            assert task_inputs["memory"] == "1024"

            # Check container definitions
            container_defs = json.loads(task_inputs["container_definitions"])
            assert len(container_defs) == 1
            container = container_defs[0]
            assert container["name"] == "dagster-webserver"
            assert container["image"] == "dagster-taskiq-demo:latest"
            assert container["stop_timeout"] == 30

            # Check port mappings
            assert len(container["port_mappings"]) == 1
            port_mapping = container["port_mappings"][0]
            assert port_mapping["container_port"] == 3000
            assert port_mapping["name"] == "dagster-web"

        return pulumi.Output.all(result.webserver_task_definition.urn, result.webserver_task_definition.__dict__).apply(
            check_webserver_task_properties
        )

    @pulumi.runtime.test
    def test_load_balancer_configuration(self):
        """Test load balancer has correct configuration."""
        mock_provider = MagicMock(spec=pulumi_aws.Provider)
        result = create_dagster_infrastructure(
            resource_name="test-dagster",
            provider=mock_provider,
            project_name="dagster-taskiq-demo",
            environment="test",
            region="us-east-1",
            vpc_id="vpc-12345678",
            subnet_ids=["subnet-12345678", "subnet-87654321"],
            container_image="dagster-taskiq-demo:latest",
            aws_endpoint_url="http://localhost:4566",
            database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo",
            cluster_name="test-cluster",
            execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        )

        def check_load_balancer_properties(args):
            _urn, lb_inputs = args
            assert lb_inputs["name"] == "dagster-taskiq-demo-alb-test"
            assert lb_inputs["load_balancer_type"] == "application"
            assert lb_inputs["internal"] is False
            assert len(lb_inputs["subnets"]) == 2
            assert "subnet-12345678" in lb_inputs["subnets"]
            assert "subnet-87654321" in lb_inputs["subnets"]

        return pulumi.Output.all(result.load_balancer.urn, result.load_balancer.__dict__).apply(
            check_load_balancer_properties
        )

    @pulumi.runtime.test
    def test_target_group_configuration(self):
        """Test target group has correct configuration."""
        mock_provider = MagicMock(spec=pulumi_aws.Provider)
        result = create_dagster_infrastructure(
            resource_name="test-dagster",
            provider=mock_provider,
            project_name="dagster-taskiq-demo",
            environment="test",
            region="us-east-1",
            vpc_id="vpc-12345678",
            subnet_ids=["subnet-12345678", "subnet-87654321"],
            container_image="dagster-taskiq-demo:latest",
            aws_endpoint_url="http://localhost:4566",
            database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue.fifo",
            cluster_name="test-cluster",
            execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        )

        def check_target_group_properties(args):
            _urn, tg_inputs = args
            assert tg_inputs["name"] == "dagster-taskiq-demo-tg-test"
            assert tg_inputs["port"] == 3000
            assert tg_inputs["protocol"] == "HTTP"
            assert tg_inputs["vpc_id"] == "vpc-12345678"
            assert tg_inputs["target_type"] == "ip"

            # Check health check configuration
            health_check = tg_inputs["health_check"]
            assert health_check["enabled"] is True
            assert health_check["healthy_threshold"] == 2
            assert health_check["interval"] == 30
            assert health_check["matcher"] == "200"
            assert health_check["path"] == "/server_info"
            assert health_check["protocol"] == "HTTP"
            assert health_check["timeout"] == 5
            assert health_check["unhealthy_threshold"] == 2

        return pulumi.Output.all(result.target_group.urn, result.target_group.__dict__).apply(
            check_target_group_properties
        )
