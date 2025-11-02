"""Tests for Dagster infrastructure module."""

import json
from collections.abc import Callable
from typing import Any, cast
from unittest.mock import MagicMock

import pulumi
import pytest

from modules.dagster import DagsterResources, create_dagster_infrastructure


class Mocks(pulumi.runtime.Mocks):
    """Mock implementation for Pulumi resources."""

    def __init__(self) -> None:
        """Initialize resource factories for Dagster mocks."""
        super().__init__()
        self._resource_factories: dict[
            str,
            Callable[[pulumi.runtime.MockResourceArgs], tuple[str | None, dict[str, str]]],
        ] = {
            "aws:ec2/securityGroup:SecurityGroup": self._build_security_group,
            "aws:iam/role:Role": self._build_iam_role,
            "aws:ecs/taskDefinition:TaskDefinition": self._build_task_definition,
            "aws:servicediscovery/privateDnsNamespace:PrivateDnsNamespace": self._build_namespace,
            "aws:servicediscovery/service:Service": self._build_service_discovery,
            "aws:lb/loadBalancer:LoadBalancer": self._build_load_balancer,
            "aws:lb/targetGroup:TargetGroup": self._build_target_group,
            "aws:lb/listener:Listener": self._build_listener,
        }
        self._last_call: pulumi.runtime.MockCallArgs | None = None

    def new_resource(self, args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        """Mock resource creation.

        Returns:
            tuple[str | None, dict[str, str]]: Mocked resource identifier and input payload.
        """
        factory = self._resource_factories.get(args.typ, self._build_default)
        return factory(args)

    def call(self, args: pulumi.runtime.MockCallArgs) -> tuple[dict[str, str], list[tuple[str, str]] | None]:
        """Mock provider calls.

        Returns:
            tuple[dict[str, str], list[tuple[str, str]] | None]: Mocked call response.
        """
        self._last_call = args
        return {}, None

    @staticmethod
    def _build_default(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return f"{args.name}_id", args.inputs

    @staticmethod
    def _build_security_group(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "arn": f"arn:aws:ec2:us-east-1:123456789012:security-group/{args.name}",
                "id": f"sg-{args.name}",
            },
        )

    @staticmethod
    def _build_iam_role(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "arn": f"arn:aws:iam::123456789012:role/{args.name}",
                "id": f"{args.name}_id",
            },
        )

    @staticmethod
    def _build_task_definition(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "arn": f"arn:aws:ecs:us-east-1:123456789012:task-definition/{args.name}",
                "id": f"{args.name}_id",
            },
        )

    @staticmethod
    def _build_namespace(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "arn": f"arn:aws:servicediscovery:us-east-1:123456789012:namespace/{args.name}",
                "id": f"ns-{args.name}",
            },
        )

    @staticmethod
    def _build_service_discovery(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "arn": f"arn:aws:servicediscovery:us-east-1:123456789012:service/{args.name}",
                "id": f"svc-{args.name}",
            },
        )

    @staticmethod
    def _build_load_balancer(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "arn": f"arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/{args.name}",
                "id": f"lb-{args.name}",
                "dns_name": f"{args.name}.us-east-1.elb.amazonaws.com",
            },
        )

    @staticmethod
    def _build_target_group(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "arn": f"arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/{args.name}",
                "id": f"tg-{args.name}",
            },
        )

    @staticmethod
    def _build_listener(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "arn": f"arn:aws:elasticloadbalancing:us-east-1:123456789012:listener/{args.name}",
                "id": f"listener-{args.name}",
            },
        )


@pytest.fixture(autouse=True)
def setup_mocks() -> None:
    """Set up Pulumi mocks for all tests."""
    pulumi.runtime.set_mocks(Mocks())


@pytest.mark.filterwarnings("ignore::DeprecationWarning:pulumi.runtime.resource")
def test_create_dagster_infrastructure(
    mock_aws_provider: MagicMock, sample_resource_args: dict[str, str | list[str]]
) -> None:
    """Test creating Dagster infrastructure returns correct structure."""
    mock_aws_provider.package = "aws"  # Add required attribute

    result = create_dagster_infrastructure(
        provider=mock_aws_provider,
        resource_name=cast("str", sample_resource_args["resource_name"]),
        project_name=cast("str", sample_resource_args["project_name"]),
        environment=cast("str", sample_resource_args["environment"]),
        region=cast("str", sample_resource_args["region"]),
        vpc_id=cast("str", sample_resource_args["vpc_id"]),
        subnet_ids=cast("list[str]", sample_resource_args["subnet_ids"]),
        container_image=cast("str", sample_resource_args["container_image"]),
        aws_endpoint_url=cast("str", sample_resource_args["aws_endpoint_url"]),
        database_endpoint=cast("str", sample_resource_args["database_endpoint"]),
        queue_url=cast("str", sample_resource_args["queue_url"]),
        cluster_name=cast("str", sample_resource_args["cluster_name"]),
        execution_role_arn=cast("str", sample_resource_args["execution_role_arn"]),
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
def test_security_group_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test security group has correct configuration.

    Returns:
        pulumi.Output[None]: Assertion on the mocked security group inputs.
    """
    result = create_dagster_infrastructure(
        resource_name="test-dagster",
        provider=mock_aws_provider,
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

    def check_security_group_properties(args: list[Any]) -> None:
        _urn, sg_inputs = args
        assert sg_inputs["vpc_id"] == "vpc-12345678"
        assert sg_inputs["name"] == "dagster-taskiq-demo-dagster-test"
        assert "Shared security group for Dagster services" in sg_inputs["description"]

    return pulumi.Output.all(result.security_group.urn, result.security_group.__dict__).apply(
        check_security_group_properties
    )


@pulumi.runtime.test
def test_task_role_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test IAM role has correct configuration.

    Returns:
        pulumi.Output[None]: Assertion on the mocked task role inputs.
    """
    result = create_dagster_infrastructure(
        resource_name="test-dagster",
        provider=mock_aws_provider,
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

    def check_task_role_properties(args: list[Any]) -> None:
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
def test_daemon_task_definition_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test daemon task definition has correct configuration.

    Returns:
        pulumi.Output[None]: Assertion on the daemon task definition inputs.
    """
    result = create_dagster_infrastructure(
        resource_name="test-dagster",
        provider=mock_aws_provider,
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

    def check_daemon_task_properties(args: list[Any]) -> None:
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
        assert container["stopTimeout"] == 120

    return pulumi.Output.all(result.daemon_task_definition.urn, result.daemon_task_definition.__dict__).apply(
        check_daemon_task_properties
    )


@pulumi.runtime.test
def test_webserver_task_definition_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test webserver task definition has correct configuration.

    Returns:
        pulumi.Output[None]: Assertion on the webserver task definition inputs.
    """
    result = create_dagster_infrastructure(
        resource_name="test-dagster",
        provider=mock_aws_provider,
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

    def check_webserver_task_properties(args: list[Any]) -> None:
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
        assert container["stopTimeout"] == 30

        # Check port mappings
        assert len(container["portMappings"]) == 1
        port_mapping = container["portMappings"][0]
        assert port_mapping["containerPort"] == 3000
        assert port_mapping["name"] == "dagster-web"

    return pulumi.Output.all(result.webserver_task_definition.urn, result.webserver_task_definition.__dict__).apply(
        check_webserver_task_properties
    )


@pulumi.runtime.test
def test_load_balancer_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test load balancer has correct configuration.

    Returns:
        pulumi.Output[None]: Assertion on the load balancer inputs.
    """
    result = create_dagster_infrastructure(
        resource_name="test-dagster",
        provider=mock_aws_provider,
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

    def check_load_balancer_properties(args: list[Any]) -> None:
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
def test_target_group_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test target group has correct configuration.

    Returns:
        pulumi.Output[None]: Assertion on the target group inputs.
    """
    result = create_dagster_infrastructure(
        resource_name="test-dagster",
        provider=mock_aws_provider,
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

    def check_target_group_properties(args: list[Any]) -> None:
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

    return pulumi.Output.all(result.target_group.urn, result.target_group.__dict__).apply(check_target_group_properties)
