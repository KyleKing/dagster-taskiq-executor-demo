import os
import warnings
from typing import Any, Optional

from taskiq import AsyncBroker

from dagster_taskiq.broker import create_sqs_broker
from dagster_taskiq.defaults import (
    aws_region_name,
    sqs_endpoint_url,
    sqs_queue_url,
    s3_bucket_name,
    s3_endpoint_url,
    visibility_timeout,
    wait_time_seconds,
    worker_max_messages,
)


def make_app(app_args: Optional[dict[str, Any]] = None) -> AsyncBroker:
    """Create a taskiq broker with SQS backend and S3 result backend.

    Args:
        app_args: Optional configuration arguments for the broker

    Returns:
        Configured AsyncBroker instance
    """
    # Extract configuration from app_args or use defaults
    config = app_args or {}

    # Get SQS configuration
    queue_url = config.get("queue_url", sqs_queue_url)
    sqs_endpoint = config.get("endpoint_url", sqs_endpoint_url)
    region_name = config.get("region_name", aws_region_name)
    config_source = config.get("config_source")
    if isinstance(config_source, dict):
        source_overrides = config_source
    elif config_source is None:
        source_overrides = {}
    else:
        source_overrides = getattr(config_source, "__dict__", {})
        if not isinstance(source_overrides, dict):
            source_overrides = {}

    # Get S3 configuration
    s3_bucket = config.get("s3_bucket_name", s3_bucket_name)
    s3_endpoint = config.get("s3_endpoint_url", s3_endpoint_url)

    # Get AWS credentials from environment or config
    aws_access_key_id = config.get("aws_access_key_id", os.getenv("AWS_ACCESS_KEY_ID"))
    aws_secret_access_key = config.get(
        "aws_secret_access_key", os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    # Get worker configuration
    max_messages = config.get("max_number_of_messages", worker_max_messages)
    wait_time = config.get("wait_time_seconds", wait_time_seconds)
    visibility = config.get("visibility_timeout", visibility_timeout)

    # Create S3 result backend
    try:
        from taskiq_aio_sqs import S3Backend
        result_backend = S3Backend(
            bucket_name=s3_bucket,
            endpoint_url=s3_endpoint,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
    except ImportError:
        raise ImportError("taskiq-aio-sqs is required for S3 backend support")

    # Determine fair-queue configuration. Taskiq fair queues require FIFO URLs.
    queue_is_fifo = str(queue_url or "").lower().endswith(".fifo")
    requested_fair_queue = config.get("is_fair_queue")
    if requested_fair_queue is None:
        requested_fair_queue = source_overrides.get("is_fair_queue")

    if requested_fair_queue is None:
        is_fair_queue = queue_is_fifo
    elif requested_fair_queue and not queue_is_fifo:
        warnings.warn(
            'Ignoring "is_fair_queue=True" because the configured queue URL is not FIFO.',
            UserWarning,
            stacklevel=2,
        )
        is_fair_queue = False
    else:
        is_fair_queue = bool(requested_fair_queue)

    # Create the SQS broker with S3 result backend, extended messages, and fair queuing
    broker = create_sqs_broker(
        queue_url=queue_url,
        endpoint_url=sqs_endpoint,
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        max_number_of_messages=max_messages,
        wait_time_seconds=wait_time,
        visibility_timeout=visibility,
        result_backend=result_backend,
        s3_extended_bucket_name=s3_bucket,  # Enable extended messages for large payloads
        is_fair_queue=is_fair_queue,
    )

    return broker
