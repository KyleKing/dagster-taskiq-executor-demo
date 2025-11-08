"""Helpers for constructing Taskiq SQS brokers."""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

# Import will be available after dependency installation.
try:  # pragma: no cover - exercised in integration tests
    from taskiq_aio_sqs import SQSBroker as TaskiqSQSBroker
except ImportError:  # pragma: no cover - best effort without dependency
    TaskiqSQSBroker = None  # type: ignore[assignment,misc]

from pydantic import BaseModel, ConfigDict


def _queue_name_from_url(queue_url: str) -> str:
    parts = queue_url.rstrip("/").split("/")
    queue_name = parts[-1] if parts and parts[-1] else ""
    if not queue_name:
        msg = f"Unable to derive queue name from URL: {queue_url!r}"
        raise ValueError(msg)
    return queue_name


class SqsBrokerConfig(BaseModel):
    """Configuration payload for constructing taskiq-aio-sqs brokers.

    Uses Pydantic for validation and type safety. All fields are validated
    on instantiation to catch configuration errors early.
    """

    queue_url: str = Field(..., description="SQS queue URL")
    endpoint_url: str | None = Field(None, description="Custom AWS endpoint URL (for LocalStack)")
    region_name: str = Field("us-east-1", description="AWS region name")
    aws_access_key_id: str | None = Field(None, description="AWS access key ID")
    aws_secret_access_key: str | None = Field(None, description="AWS secret access key")
    wait_time_seconds: int = Field(20, ge=0, le=20, description="SQS long polling wait time (0-20 seconds)")
    max_number_of_messages: int = Field(1, ge=1, le=10, description="Maximum messages to receive per poll (1-10)")
    delay_seconds: int = Field(0, ge=0, le=900, description="Message delay in seconds (0-900)")
    is_fair_queue: bool = Field(False, description="Enable fair queue (FIFO) mode")
    use_task_id_for_deduplication: bool = Field(False, description="Use task ID for FIFO deduplication")
    s3_extended_bucket_name: str | None = Field(None, description="S3 bucket for extended payloads (>256KB)")
    extra_options: dict[str, Any] = Field(default_factory=dict, description="Additional broker options")

    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("queue_url")
    @classmethod
    def validate_queue_url(cls, v: str) -> str:
        """Validate queue URL format."""
        if not v or not v.strip():
            msg = "queue_url cannot be empty"
            raise ValueError(msg)
        if not v.startswith(("http://", "https://")):
            msg = f"queue_url must be a valid URL, got: {v!r}"
            raise ValueError(msg)
        return v.strip()

    @model_validator(mode="after")
    def validate_fair_queue_config(self) -> "SqsBrokerConfig":
        """Warn if fair queue is enabled but queue URL is not FIFO."""
        if self.is_fair_queue and not self.queue_url.lower().endswith(".fifo"):
            import warnings

            warnings.warn(
                'is_fair_queue=True but queue URL does not end with ".fifo". '
                "Fair queue mode requires a FIFO queue.",
                UserWarning,
                stacklevel=2,
            )
        return self

    @property
    def queue_name(self) -> str:
        """Get the queue name extracted from the queue URL.

        Returns:
            The queue name
        """
        return _queue_name_from_url(self.queue_url)

    def as_kwargs(self) -> dict[str, Any]:
        """Convert configuration to keyword arguments for broker creation.

        Returns:
            Dictionary of keyword arguments
        """
        return {
            "endpoint_url": self.endpoint_url,
            "sqs_queue_name": self.queue_name,
            "region_name": self.region_name,
            "aws_access_key_id": self.aws_access_key_id,
            "aws_secret_access_key": self.aws_secret_access_key,
            "wait_time_seconds": self.wait_time_seconds,
            "max_number_of_messages": self.max_number_of_messages,
            "delay_seconds": self.delay_seconds,
            "is_fair_queue": self.is_fair_queue,
            "use_task_id_for_deduplication": self.use_task_id_for_deduplication,
            "s3_extended_bucket_name": self.s3_extended_bucket_name,
        } | self.extra_options

    def create_broker(self, *, result_backend: Any | None = None) -> Any:
        """Create a Taskiq broker instance from this configuration.

        Args:
            result_backend: Optional result backend to attach to the broker

        Returns:
            Configured TaskiqSQSBroker instance

        Raises:
            ImportError: If taskiq-aio-sqs is not installed
        """
        if TaskiqSQSBroker is None:  # pragma: no cover - import checked above
            raise ImportError("taskiq-aio-sqs is required for SQS broker support")

        broker = TaskiqSQSBroker(**self.as_kwargs())
        if result_backend is not None:
            broker = broker.with_result_backend(result_backend)
        return broker


__all__ = ["SqsBrokerConfig", "_queue_name_from_url"]
