"""Tests for SQS FIFO queue component."""

import json
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pulumi
import pulumi_aws
import pytest

from components.sqs_fifo import QueueResources, attach_queue_access_policy, create_fifo_queue_with_dlq


class Mocks(pulumi.runtime.Mocks):
    """Mock implementation for Pulumi resources."""

    def __init__(self) -> None:
        """Initialize resource factories for queue mocks."""
        super().__init__()
        self._resource_factories: dict[
            str,
            Callable[[pulumi.runtime.MockResourceArgs], tuple[str | None, dict[str, str]]],
        ] = {
            "aws:sqs/queue:Queue": self._build_queue,
            "aws:sqs/queuePolicy:QueuePolicy": self._build_queue_policy,
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
        return args.name + "_id", args.inputs

    @staticmethod
    def _build_queue(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        queue_name = args.inputs.get("name", args.name)
        outputs = {
            **args.inputs,
            "arn": f"arn:aws:sqs:us-east-1:123456789012:{queue_name}",
            "id": f"https://sqs.us-east-1.amazonaws.com/123456789012/{queue_name}",
        }
        return args.name + "_id", outputs

    @staticmethod
    def _build_queue_policy(args: pulumi.runtime.MockResourceArgs) -> tuple[str | None, dict[str, str]]:
        return args.name + "_id", args.inputs


@pytest.fixture(autouse=True)
def setup_mocks() -> None:
    """Set up Pulumi mocks for all tests."""
    pulumi.runtime.set_mocks(Mocks())


def test_create_fifo_queue_with_dlq(mock_aws_provider: MagicMock) -> None:
    """Test creating FIFO queue with DLQ returns correct structure."""
    result = create_fifo_queue_with_dlq(
        resource_name="test-queue",
        provider=mock_aws_provider,
        queue_name="test-taskiq.fifo",
        dlq_name="test-taskiq-dlq.fifo",
        message_retention_seconds=1209600,
        queue_visibility_timeout=300,
        dlq_visibility_timeout=300,
        redrive_max_receive_count=3,
    )

    assert isinstance(result, QueueResources)
    assert result.queue is not None
    assert result.dead_letter_queue is not None


@pulumi.runtime.test
def test_fifo_queue_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test FIFO queue has correct configuration.

    Returns:
        pulumi.Output[None]: Assertion on the FIFO queue inputs.
    """
    result = create_fifo_queue_with_dlq(
        resource_name="test-queue",
        provider=mock_aws_provider,
        queue_name="test-taskiq.fifo",
        dlq_name="test-taskiq-dlq.fifo",
        message_retention_seconds=1209600,
        queue_visibility_timeout=300,
        dlq_visibility_timeout=300,
        redrive_max_receive_count=3,
    )

    def check_fifo_properties(args: list[Any]) -> None:
        _urn, queue_inputs = args
        assert queue_inputs["fifo_queue"] is True
        assert queue_inputs["content_based_deduplication"] is True
        assert queue_inputs["deduplication_scope"] == "messageGroup"
        assert queue_inputs["fifo_throughput_limit"] == "perMessageGroupId"
        assert queue_inputs["visibility_timeout_seconds"] == 300
        assert queue_inputs["message_retention_seconds"] == 1209600
        assert queue_inputs["delay_seconds"] == 0
        assert queue_inputs["receive_wait_time_seconds"] == 20
        assert queue_inputs["max_message_size"] == 262144

    return pulumi.Output.all(result.queue.urn, result.queue.__dict__).apply(check_fifo_properties)


@pulumi.runtime.test
def test_dlq_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test DLQ has correct configuration.

    Returns:
        pulumi.Output[None]: Assertion on the dead-letter queue inputs.
    """
    result = create_fifo_queue_with_dlq(
        resource_name="test-queue",
        provider=mock_aws_provider,
        queue_name="test-taskiq.fifo",
        dlq_name="test-taskiq-dlq.fifo",
        message_retention_seconds=1209600,
        queue_visibility_timeout=300,
        dlq_visibility_timeout=300,
        redrive_max_receive_count=3,
    )

    def check_dlq_properties(args: list[Any]) -> None:
        _urn, dlq_inputs = args
        assert dlq_inputs["fifo_queue"] is True
        assert dlq_inputs["content_based_deduplication"] is True
        assert dlq_inputs["deduplication_scope"] == "messageGroup"
        assert dlq_inputs["fifo_throughput_limit"] == "perMessageGroupId"
        assert dlq_inputs["visibility_timeout_seconds"] == 300
        assert dlq_inputs["message_retention_seconds"] == 1209600

    return pulumi.Output.all(result.dead_letter_queue.urn, result.dead_letter_queue.__dict__).apply(
        check_dlq_properties
    )


@pulumi.runtime.test
def test_redrive_policy_configuration(mock_aws_provider: MagicMock) -> pulumi.Output[None]:
    """Test main queue has correct redrive policy.

    Returns:
        pulumi.Output[None]: Assertion on the redrive policy configuration.
    """
    result = create_fifo_queue_with_dlq(
        resource_name="test-queue",
        provider=mock_aws_provider,
        queue_name="test-taskiq.fifo",
        dlq_name="test-taskiq-dlq.fifo",
        message_retention_seconds=1209600,
        queue_visibility_timeout=300,
        dlq_visibility_timeout=300,
        redrive_max_receive_count=3,
    )

    def check_redrive_policy(args: list[Any]) -> None:
        _urn, redrive_policy = args
        policy = json.loads(redrive_policy)
        assert "deadLetterTargetArn" in policy
        assert "maxReceiveCount" in policy
        assert policy["maxReceiveCount"] == 3
        # The component creates a list with the ARN
        dlq_arn_list = policy["deadLetterTargetArn"]
        assert isinstance(dlq_arn_list, list)
        assert len(dlq_arn_list) == 1
        # dlq_arn_list[0] is itself a list containing the ARN string
        dlq_arn = dlq_arn_list[0][0] if isinstance(dlq_arn_list[0], list) else dlq_arn_list[0]
        assert "test-taskiq-dlq" in dlq_arn

    return pulumi.Output.all(result.queue.urn, result.queue.redrive_policy).apply(check_redrive_policy)


def test_attach_queue_access_policy(mock_aws_provider: MagicMock) -> None:
    """Test attaching queue access policy."""
    # Mock queue resources
    mock_queue = MagicMock(spec=pulumi_aws.sqs.Queue)
    mock_queue.arn = pulumi.Output.from_input("arn:aws:sqs:us-east-1:123456789012:test-queue")
    mock_queue.id = pulumi.Output.from_input("test-queue-url")

    mock_dlq = MagicMock(spec=pulumi_aws.sqs.Queue)
    mock_dlq.arn = pulumi.Output.from_input("arn:aws:sqs:us-east-1:123456789012:test-dlq")
    mock_dlq.id = pulumi.Output.from_input("test-dlq-url")

    queues = QueueResources(queue=mock_queue, dead_letter_queue=mock_dlq)
    principal_arns = pulumi.Output.from_input(["arn:aws:iam::123456789012:role/test-role"])
    actions = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage"]

    # This should not raise an exception
    attach_queue_access_policy(
        policy_name="test-policy",
        provider=mock_aws_provider,
        queues=queues,
        principal_arns=principal_arns,
        actions=actions,
    )
