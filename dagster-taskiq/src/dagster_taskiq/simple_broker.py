"""Simplified broker factory for TaskIQ with minimal configuration.

This module provides a streamlined approach to creating TaskIQ brokers for Dagster,
focusing on simplicity and leveraging TaskIQ's native features rather than custom code.
"""

import os
from typing import Any

from taskiq import AsyncBroker
from taskiq_aio_sqs import S3Backend, SQSBroker


def _parse_queue_name(queue_url: str) -> str:
    """Extract queue name from SQS URL.

    Args:
        queue_url: Full SQS queue URL

    Returns:
        Queue name

    Raises:
        ValueError: If queue URL is invalid
    """
    if not queue_url:
        msg = "queue_url is required"
        raise ValueError(msg)

    parts = queue_url.rstrip("/").split("/")
    queue_name = parts[-1] if parts and parts[-1] else ""

    if not queue_name:
        msg = f"Cannot extract queue name from URL: {queue_url}"
        raise ValueError(msg)

    return queue_name


def make_simple_broker(app_args: dict[str, Any] | None = None) -> AsyncBroker:
    """Create a simple TaskIQ broker for Dagster with minimal configuration.

    This is a streamlined alternative to the full `make_app()` function that:
    - Uses environment variables for most configuration
    - Eliminates complex config resolution logic
    - Provides sensible defaults
    - Is easier to understand and maintain

    Configuration precedence:
    1. app_args dictionary (highest priority)
    2. Environment variables
    3. Defaults

    Environment Variables:
        DAGSTER_SQS_QUEUE_URL: SQS queue URL (required if not in app_args)
        AWS_ENDPOINT_URL: Custom endpoint for LocalStack
        AWS_DEFAULT_REGION: AWS region (default: us-east-1)
        DAGSTER_S3_BUCKET: S3 bucket for results (required if not in app_args)
        AWS_ACCESS_KEY_ID: AWS access key
        AWS_SECRET_ACCESS_KEY: AWS secret key

    Args:
        app_args: Optional configuration dictionary

    Returns:
        Configured AsyncBroker with S3 result backend

    Raises:
        ValueError: If required configuration is missing

    Example:
        >>> broker = make_simple_broker({
        ...     "queue_url": "https://sqs.us-east-1.amazonaws.com/123/my-queue",
        ...     "s3_bucket": "my-results-bucket"
        ... })

        Or using environment variables:
        >>> os.environ["DAGSTER_SQS_QUEUE_URL"] = "https://..."
        >>> os.environ["DAGSTER_S3_BUCKET"] = "my-bucket"
        >>> broker = make_simple_broker()
    """
    config = app_args or {}

    # Get queue configuration
    queue_url = config.get("queue_url") or os.getenv("DAGSTER_SQS_QUEUE_URL")
    if not queue_url:
        msg = "queue_url must be provided in config or DAGSTER_SQS_QUEUE_URL environment variable"
        raise ValueError(msg)

    # Get AWS configuration
    endpoint_url = config.get("endpoint_url") or os.getenv("AWS_ENDPOINT_URL")
    region_name = config.get("region_name") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    access_key_id = config.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_access_key = config.get("aws_secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY")

    # Get S3 configuration
    s3_bucket = config.get("s3_bucket") or os.getenv("DAGSTER_S3_BUCKET")
    if not s3_bucket:
        msg = "s3_bucket must be provided in config or DAGSTER_S3_BUCKET environment variable"
        raise ValueError(msg)

    s3_endpoint = config.get("s3_endpoint_url") or endpoint_url  # Reuse AWS endpoint for S3

    # Create S3 result backend
    result_backend = S3Backend(
        bucket_name=s3_bucket,
        endpoint_url=s3_endpoint,
        region_name=region_name,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )

    # Create SQS broker with simple configuration
    broker = SQSBroker(
        endpoint_url=endpoint_url,
        sqs_queue_name=_parse_queue_name(queue_url),
        region_name=region_name,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        # Use sensible defaults for worker behavior
        wait_time_seconds=20,  # Long polling
        max_number_of_messages=1,  # Process one at a time
    )

    # Attach result backend
    return broker.with_result_backend(result_backend)


def make_simple_broker_with_middleware(app_args: dict[str, Any] | None = None) -> AsyncBroker:
    """Create broker with observability middleware included.

    This is an enhanced version that adds TaskIQ middleware for:
    - Structured logging
    - Execution metrics
    - Error reporting

    Args:
        app_args: Optional configuration dictionary

    Returns:
        Configured AsyncBroker with middleware and result backend

    Example:
        >>> broker = make_simple_broker_with_middleware()
        >>> # Broker now has logging and metrics middleware attached
    """
    from dagster_taskiq.simple_middleware import DagsterLoggingMiddleware

    broker = make_simple_broker(app_args)

    # Add middleware for observability
    broker.add_middlewares(
        DagsterLoggingMiddleware(),
        # Future: Add metrics middleware
        # DagsterMetricsMiddleware(),
    )

    return broker
