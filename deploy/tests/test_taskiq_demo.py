"""Tests for the TaskIQ demo Pulumi module."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pulumi
import pytest

from modules.taskiq_demo import TaskiqDemoResources, create_taskiq_demo_infrastructure


class DemoMocks(pulumi.runtime.Mocks):
    """Pulumi mocks that provide predictable resource IDs."""

    def __init__(self) -> None:
        super().__init__()
        self._resource_factories: dict[
            str,
            Callable[[pulumi.runtime.MockResourceArgs], tuple[str | None, dict[str, Any]]],
        ] = {
            "aws:sqs/queue:Queue": self._mock_queue,
            "aws:ec2/securityGroup:SecurityGroup": self._with_ids,
            "aws:ec2/securityGroupRule:SecurityGroupRule": self._with_ids,
            "aws:cloudwatch/logGroup:LogGroup": self._with_ids,
            "aws:iam/role:Role": self._mock_role,
            "aws:iam/rolePolicy:RolePolicy": self._with_ids,
            "aws:ecs/taskDefinition:TaskDefinition": self._mock_task_definition,
            "aws:ecs/service:Service": self._with_ids,
        }

    def new_resource(self, args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, Any]]:
        factory = self._resource_factories.get(args.typ, self._with_ids)
        return factory(args)

    def call(self, args: pulumi.runtime.MockCallArgs) -> tuple[dict[str, Any], list[tuple[str, str]] | None]:
        return {}, None

    @staticmethod
    def _with_ids(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, Any]]:
        return f"{args.name}_id", {**args.inputs, "id": f"{args.name}_id"}

    @staticmethod
    def _mock_queue(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, Any]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "id": f"https://sqs.us-east-1.amazonaws.com/000000000000/{args.name}",
                "arn": f"arn:aws:sqs:us-east-1:000000000000:{args.name}",
            },
        )

    @staticmethod
    def _mock_role(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, Any]]:
        return (
            f"{args.name}_id",
            {**args.inputs, "arn": f"arn:aws:iam::000000000000:role/{args.name}", "id": f"{args.name}_id"},
        )

    @staticmethod
    def _mock_task_definition(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, Any]]:
        return (
            f"{args.name}_id",
            {
                **args.inputs,
                "arn": f"arn:aws:ecs:us-east-1:000000000000:task-definition/{args.name}",
                "id": f"{args.name}_id",
            },
        )


@pytest.fixture(autouse=True)
def configure_mocks() -> None:
    """Configure Pulumi to use test doubles."""
    pulumi.runtime.set_mocks(DemoMocks())


def test_create_taskiq_demo_infrastructure(mock_aws_provider: MagicMock) -> None:
    """Ensure the module returns a populated dataclass."""
    resources = create_taskiq_demo_infrastructure(
        resource_name="demo",
        provider=mock_aws_provider,
        project_name="demo-project",
        environment="test",
        region="us-east-1",
        cluster_arn="arn:aws:ecs:us-east-1:000000000000:cluster/demo",
        vpc_id="vpc-12345678",
        subnet_ids=["subnet-1234abcd", "subnet-abcd1234"],
        container_image="123456789012.dkr.ecr.us-east-1.amazonaws.com/demo:taskiq-demo",
        aws_endpoint_url="http://localhost:4566",
        aws_access_key="test",
        aws_secret_key="test",
        queue_name="taskiq-demo",
        message_retention_seconds=604800,
        visibility_timeout=120,
        execution_role_arn="arn:aws:iam::000000000000:role/ecsTaskExecutionRole",
        api_desired_count=1,
        worker_desired_count=1,
        assign_public_ip=True,
    )

    assert isinstance(resources, TaskiqDemoResources)
    assert resources.queue is not None
    assert resources.api_service is not None
    assert resources.worker_service is not None


@pulumi.runtime.test
def test_api_container_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Verify API task definition sets expected environment variables."""
    resources = create_taskiq_demo_infrastructure(
        resource_name="demo",
        provider=mock_aws_provider,
        project_name="demo-project",
        environment="test",
        region="us-east-1",
        cluster_arn="arn:aws:ecs:us-east-1:000000000000:cluster/demo",
        vpc_id="vpc-12345678",
        subnet_ids=["subnet-1234abcd"],
        container_image="123456789012.dkr.ecr.us-east-1.amazonaws.com/demo:taskiq-demo",
        aws_endpoint_url="http://localhost:4566",
        aws_access_key="test",
        aws_secret_key="test",
        queue_name="taskiq-demo",
        message_retention_seconds=604800,
        visibility_timeout=120,
        execution_role_arn="arn:aws:iam::000000000000:role/ecsTaskExecutionRole",
        api_desired_count=1,
        worker_desired_count=1,
        assign_public_ip=True,
    )

    def _assert_env(container_json: str) -> None:
        values = json.loads(container_json)
        env = {item["name"]: item["value"] for item in values[0]["environment"]}
        assert env["SERVICE_ROLE"] == "api"
        assert env["TASKIQ_DEMO_SQS_QUEUE_NAME"] == "taskiq-demo"
        assert env["TASKIQ_DEMO_SQS_ENDPOINT_URL"] == "http://localhost:4566"
        assert env["TASKIQ_DEMO_AWS_REGION"] == "us-east-1"

    return resources.api_task_definition.container_definitions.apply(_assert_env)
