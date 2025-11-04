"""Helpers for constructing Taskiq SQS brokers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Import will be available after dependency installation.
try:  # pragma: no cover - exercised in integration tests
    from taskiq_aio_sqs import SQSBroker as TaskiqSQSBroker
except ImportError:  # pragma: no cover - best effort without dependency
    TaskiqSQSBroker = None  # type: ignore[assignment]


def _queue_name_from_url(queue_url: str) -> str:
    parts = queue_url.rstrip("/").split("/")
    queue_name = parts[-1] if parts and parts[-1] else ""
    if not queue_name:
        msg = f"Unable to derive queue name from URL: {queue_url!r}"
        raise ValueError(msg)
    return queue_name


@dataclass(frozen=True)
class SqsBrokerConfig:
    """Configuration payload for constructing taskiq-aio-sqs brokers."""

    queue_url: str
    endpoint_url: str | None = None
    region_name: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    wait_time_seconds: int = 20
    max_number_of_messages: int = 1
    delay_seconds: int = 0
    is_fair_queue: bool = False
    use_task_id_for_deduplication: bool = False
    s3_extended_bucket_name: str | None = None
    extra_options: dict[str, Any] = field(default_factory=dict)

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
