import os
from typing import Any, Optional

from taskiq import AsyncBroker

from dagster_taskiq.broker import SQSBroker
from dagster_taskiq.defaults import (
    aws_region_name,
    sqs_endpoint_url,
    sqs_queue_url,
    visibility_timeout,
    wait_time_seconds,
    worker_max_messages,
)


def make_app(app_args: Optional[dict[str, Any]] = None) -> AsyncBroker:
    """Create a taskiq broker with SQS backend.

    Args:
        app_args: Optional configuration arguments for the broker

    Returns:
        Configured AsyncBroker instance
    """
    # Extract configuration from app_args or use defaults
    config = app_args or {}

    # Get SQS configuration
    queue_url = config.get("queue_url", sqs_queue_url)
    endpoint_url = config.get("endpoint_url", sqs_endpoint_url)
    region_name = config.get("region_name", aws_region_name)

    # Get AWS credentials from environment or config
    aws_access_key_id = config.get("aws_access_key_id", os.getenv("AWS_ACCESS_KEY_ID"))
    aws_secret_access_key = config.get(
        "aws_secret_access_key", os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    # Get worker configuration
    max_messages = config.get("max_number_of_messages", worker_max_messages)
    wait_time = config.get("wait_time_seconds", wait_time_seconds)
    visibility = config.get("visibility_timeout", visibility_timeout)

    # Create the SQS broker
    broker = SQSBroker(
        queue_url=queue_url,
        endpoint_url=endpoint_url,
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        max_number_of_messages=max_messages,
        wait_time_seconds=wait_time,
        visibility_timeout=visibility,
    )

    return broker
