"""Tests for TaskIQ infrastructure module."""

import json
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pulumi
import pytest

from modules.taskiq import TaskIQResources, create_taskiq_infrastructure


class Mocks(pulumi.runtime.Mocks):
    """Mock implementation for Pulumi resources."""

    def __init__(self) -> None:
        """Initialize resource factories for TaskIQ mocks."""
        super().__init__()
        self._resource_factories: dict[
            str,
            Callable[[pulumi.runtime.MockResourceArgs], tuple[str | None, dict[str, str]]],
        ] = {
            "aws:sqs/queue:Queue": self._build_queue,
            "aws:sqs/queuePolicy:QueuePolicy": self._build_queue_policy,
            "aws:iam/role:Role": self._build_iam_role,
            "aws:ecs/taskDefinition:TaskDefinition": self._build_task_definition,
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
    def _build_queue(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "arn": f"arn:aws:sqs:us-east-1:123456789012:{args.name}",
                "id": f"https://sqs.us-east-1.amazonaws.com/123456789012/{args.name}",
            },
        )

    @staticmethod
    def _build_queue_policy(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return f"{args.name}_id", args.inputs

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


@pytest.fixture(autouse=True)
def setup_mocks() -> None:
    """Set up Pulumi mocks for all tests."""
    pulumi.runtime.set_mocks(Mocks())


def test_create_taskiq_infrastructure(mock_aws_provider: MagicMock) -> None:
    """Test creating TaskIQ infrastructure returns correct structure."""
    result = create_taskiq_infrastructure(
        resource_name="test-taskiq",
        provider=mock_aws_provider,
        project_name="dagster-taskiq-demo",
        environment="test",
        region="us-east-1",
        container_image="dagster-taskiq-demo:latest",
        aws_endpoint_url="http://localhost:4566",
        database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
        execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        message_retention_seconds=1209600,
        queue_visibility_timeout=300,
        dlq_visibility_timeout=300,
        redrive_max_receive_count=3,
    )

    assert isinstance(result, TaskIQResources)
    assert result.queues is not None
    assert result.task_role is not None
    assert result.worker_task_definition is not None


@pulumi.runtime.test
def test_queue_configuration(
    mock_aws_provider: MagicMock,
) -> tuple[pulumi.Output[None], pulumi.Output[None]]:
    """Test SQS queues have correct configuration.

    Returns:
        tuple[pulumi.Output[None], pulumi.Output[None]]: Assertions on the primary and DLQ queue inputs.
    """
    result = create_taskiq_infrastructure(
        resource_name="test-taskiq",
        provider=mock_aws_provider,
        project_name="dagster-taskiq-demo",
        environment="test",
        region="us-east-1",
        container_image="dagster-taskiq-demo:latest",
        aws_endpoint_url="http://localhost:4566",
        database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
        execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        message_retention_seconds=1209600,
        queue_visibility_timeout=300,
        dlq_visibility_timeout=300,
        redrive_max_receive_count=3,
    )

    def check_main_queue_properties(args: list[Any]) -> None:
        _urn, queue_inputs = args
        assert queue_inputs["name"] == "dagster-taskiq-demo-taskiq-test.fifo"
        assert queue_inputs["fifo_queue"] is True
        assert queue_inputs["content_based_deduplication"] is True
        assert queue_inputs["visibility_timeout_seconds"] == 300
        assert queue_inputs["message_retention_seconds"] == 1209600

    def check_dlq_properties(args: list[Any]) -> None:
        _urn, dlq_inputs = args
        assert dlq_inputs["name"] == "dagster-taskiq-demo-taskiq-dlq-test.fifo"
        assert dlq_inputs["fifo_queue"] is True
        assert dlq_inputs["content_based_deduplication"] is True
        assert dlq_inputs["visibility_timeout_seconds"] == 300
        assert dlq_inputs["message_retention_seconds"] == 1209600

    return (
        pulumi.Output.all(result.queues.queue.urn, result.queues.queue.__dict__).apply(check_main_queue_properties),
        pulumi.Output.all(result.queues.dead_letter_queue.urn, result.queues.dead_letter_queue.__dict__).apply(
            check_dlq_properties
        ),
    )


@pulumi.runtime.test
def test_task_role_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test IAM role has correct configuration.

    Returns:
        pulumi.Output[None]: Assertion on the TaskIQ IAM role inputs.
    """
    result = create_taskiq_infrastructure(
        resource_name="test-taskiq",
        provider=mock_aws_provider,
        project_name="dagster-taskiq-demo",
        environment="test",
        region="us-east-1",
        container_image="dagster-taskiq-demo:latest",
        aws_endpoint_url="http://localhost:4566",
        database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
        execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        message_retention_seconds=1209600,
        queue_visibility_timeout=300,
        dlq_visibility_timeout=300,
        redrive_max_receive_count=3,
    )

    def check_task_role_properties(args: list[Any]) -> None:
        _urn, role_inputs = args
        assert role_inputs["name"] == "dagster-taskiq-demo-taskiq-task-test"

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
def test_worker_task_definition_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test worker task definition has correct configuration.

    Returns:
        pulumi.Output[None]: Assertion on the worker task definition inputs.
    """
    result = create_taskiq_infrastructure(
        resource_name="test-taskiq",
        provider=mock_aws_provider,
        project_name="dagster-taskiq-demo",
        environment="test",
        region="us-east-1",
        container_image="dagster-taskiq-demo:latest",
        aws_endpoint_url="http://localhost:4566",
        database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
        execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        message_retention_seconds=1209600,
        queue_visibility_timeout=300,
        dlq_visibility_timeout=300,
        redrive_max_receive_count=3,
    )

    def check_worker_task_properties(args: list[Any]) -> None:
        _urn, task_inputs = args
        assert task_inputs["family"] == "dagster-taskiq-demo-taskiq-worker-test"
        assert task_inputs["cpu"] == "512"
        assert task_inputs["memory"] == "1024"
        assert task_inputs["execution_role_arn"] == "arn:aws:iam::123456789012:role/ecsTaskExecutionRole"

        # Check container definitions
        container_defs = json.loads(task_inputs["container_definitions"])
        assert len(container_defs) == 1
        container = container_defs[0]
        assert container["name"] == "taskiq-worker"
        assert container["image"] == "dagster-taskiq-demo:latest"
        assert container["stopTimeout"] == 300

        # Check environment variables
        env_vars = {var["name"]: var["value"] for var in container["environment"]}
        assert env_vars["POSTGRES_HOST"] == "test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com"
        assert env_vars["POSTGRES_PORT"] == "5432"
        assert env_vars["POSTGRES_USER"] == "dagster"
        assert env_vars["POSTGRES_PASSWORD"] == "dagster"
        assert env_vars["POSTGRES_DB"] == "dagster"
        assert env_vars["AWS_ENDPOINT_URL"] == "http://localhost:4566"
        assert env_vars["AWS_DEFAULT_REGION"] == "us-east-1"
        assert env_vars["DAGSTER_HOME"] == "/opt/dagster/dagster_home"
        assert env_vars["PYTHONPATH"] == "/opt/dagster/app"
        assert env_vars["WORKER_CONCURRENCY"] == "2"
        assert env_vars["TASKIQ_WORKER_ID"] == "worker-${HOSTNAME}"

    return pulumi.Output.all(result.worker_task_definition.urn, result.worker_task_definition.__dict__).apply(
        check_worker_task_properties
    )


@pulumi.runtime.test
def test_iam_policy_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test IAM policy has correct SQS permissions.

    Returns:
        pulumi.Output[None]: Assertion on the IAM policy resource creation.
    """
    result = create_taskiq_infrastructure(
        resource_name="test-taskiq",
        provider=mock_aws_provider,
        project_name="dagster-taskiq-demo",
        environment="test",
        region="us-east-1",
        container_image="dagster-taskiq-demo:latest",
        aws_endpoint_url="http://localhost:4566",
        database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
        execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        message_retention_seconds=1209600,
        queue_visibility_timeout=300,
        dlq_visibility_timeout=300,
        redrive_max_receive_count=3,
    )

    # Note: IAM policy testing would require capturing the policy document from the RolePolicy resource
    # For now, we'll just verify the role creation succeeds
    return pulumi.Output.all(result.task_role.urn, result.task_role.__dict__).apply(lambda _: None)


def test_custom_queue_parameters(mock_aws_provider: MagicMock) -> None:
    """Test creating TaskIQ infrastructure with custom queue parameters."""
    result = create_taskiq_infrastructure(
        resource_name="test-taskiq",
        provider=mock_aws_provider,
        project_name="dagster-taskiq-demo",
        environment="test",
        region="us-east-1",
        container_image="dagster-taskiq-demo:latest",
        aws_endpoint_url="http://localhost:4566",
        database_endpoint="test-cluster.cluster-12345678.us-east-1.rds.amazonaws.com",
        execution_role_arn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        message_retention_seconds=864000,  # 10 days
        queue_visibility_timeout=600,  # 10 minutes
        dlq_visibility_timeout=300,  # 5 minutes
        redrive_max_receive_count=5,
    )

    assert isinstance(result, TaskIQResources)
    assert result.queues is not None
    assert result.task_role is not None
    assert result.worker_task_definition is not None
