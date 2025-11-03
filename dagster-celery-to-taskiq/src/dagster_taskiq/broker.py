"""SQS broker implementation using taskiq-aio-sqs with S3 backend."""

from typing import Any, Optional

# Import will be available after dependency installation
try:
    from taskiq_aio_sqs import SQSBroker as AioSQSBroker, S3Backend
except ImportError:
    AioSQSBroker = None
    S3Backend = None


def create_sqs_broker(
    queue_url: str,
    endpoint_url: Optional[str] = None,
    region_name: str = "us-east-1",
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    max_number_of_messages: int = 1,
    wait_time_seconds: int = 20,
    visibility_timeout: int = 300,
    result_backend: Optional[Any] = None,
    s3_extended_bucket_name: Optional[str] = None,
    **kwargs: Any,
) -> Any:
    """Create SQS broker with S3 backend support.

    Args:
        queue_url: SQS queue URL
        endpoint_url: Custom AWS endpoint (for LocalStack)
        region_name: AWS region name
        aws_access_key_id: AWS access key
        aws_secret_access_key: AWS secret key
        max_number_of_messages: Max messages per receive call
        wait_time_seconds: Long polling wait time
        visibility_timeout: Message visibility timeout (unused, kept for compatibility)
        result_backend: Optional result backend
        s3_extended_bucket_name: S3 bucket for extended messages
        **kwargs: Additional broker arguments

    Returns:
        Configured SQS broker instance
    """
    if AioSQSBroker is None:
        raise ImportError("taskiq-aio-sqs is required for S3 backend support")

    # Extract queue name from URL for taskiq-aio-sqs
    queue_name = queue_url.split("/")[-1]

    broker = AioSQSBroker(
        endpoint_url=endpoint_url,
        sqs_queue_name=queue_name,
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        max_number_of_messages=max_number_of_messages,
        wait_time_seconds=wait_time_seconds,
        delay_seconds=0,  # Delay handled per task via labels
        s3_extended_bucket_name=s3_extended_bucket_name,
        **kwargs,
    )

    # Add result backend if provided
    if result_backend is not None:
        broker = broker.with_result_backend(result_backend)

    return broker


# Backward compatibility alias
SQSBroker = create_sqs_broker
