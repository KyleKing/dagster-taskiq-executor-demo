"""SQS FIFO queue component with an attached dead-letter queue."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

import pulumi
from pulumi_aws import Provider, sqs


@dataclass
class QueueResources:
    """Resources created for the TaskIQ queue."""

    queue: sqs.Queue
    dead_letter_queue: sqs.Queue


def create_fifo_queue_with_dlq(
    resource_name: str,
    *,
    provider: Provider,
    queue_name: str,
    dlq_name: str,
    message_retention_seconds: int,
    queue_visibility_timeout: int,
    dlq_visibility_timeout: int,
    redrive_max_receive_count: int,
) -> QueueResources:
    """Create the FIFO queue and paired dead-letter queue.

    Returns:
        QueueResources: Wrapper containing FIFO and dead-letter queues.
    """
    dead_letter_queue = sqs.Queue(
        f"{resource_name}-dlq",
        name=dlq_name,
        fifo_queue=True,
        content_based_deduplication=True,
        deduplication_scope="messageGroup",
        fifo_throughput_limit="perMessageGroupId",
        visibility_timeout_seconds=dlq_visibility_timeout,
        message_retention_seconds=message_retention_seconds,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    redrive_policy = pulumi.Output.all(dead_letter_queue.arn).apply(
        lambda dql_arn: json.dumps({
            "deadLetterTargetArn": dql_arn,
            "maxReceiveCount": redrive_max_receive_count,
        })
    )

    queue = sqs.Queue(
        f"{resource_name}-queue",
        name=queue_name,
        fifo_queue=True,
        content_based_deduplication=True,
        deduplication_scope="messageGroup",
        fifo_throughput_limit="perMessageGroupId",
        visibility_timeout_seconds=queue_visibility_timeout,
        message_retention_seconds=message_retention_seconds,
        delay_seconds=0,
        receive_wait_time_seconds=20,
        max_message_size=262144,
        redrive_policy=redrive_policy,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    return QueueResources(queue=queue, dead_letter_queue=dead_letter_queue)


def attach_queue_access_policy(
    policy_name: str,
    *,
    provider: Provider,
    queues: QueueResources,
    principal_arns: pulumi.Input[Sequence[str]],
    actions: Sequence[str],
) -> None:
    """Attach queue policies granting the provided principals access."""

    def _policy_doc(resource_arn: str, principals: Sequence[str]) -> str:
        principal_values = list(principals)
        principal: str | Sequence[str]
        principal = principal_values[0] if len(principal_values) == 1 else principal_values

        return json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": f"{policy_name}-access",
                    "Effect": "Allow",
                    "Principal": {"AWS": principal},
                    "Action": list(actions),
                    "Resource": resource_arn,
                }
            ],
        })

    formatted_policy = pulumi.Output.all(queues.queue.arn, principal_arns).apply(lambda args: _policy_doc(*args))

    sqs.QueuePolicy(
        f"{policy_name}-queue-policy",
        queue_url=queues.queue.id,
        policy=formatted_policy,
        opts=pulumi.ResourceOptions(provider=provider),
    )

    formatted_dlq_policy = pulumi.Output.all(queues.dead_letter_queue.arn, principal_arns).apply(
        lambda args: _policy_doc(*args)
    )

    sqs.QueuePolicy(
        f"{policy_name}-dlq-policy",
        queue_url=queues.dead_letter_queue.id,
        policy=formatted_dlq_policy,
        opts=pulumi.ResourceOptions(provider=provider),
    )
