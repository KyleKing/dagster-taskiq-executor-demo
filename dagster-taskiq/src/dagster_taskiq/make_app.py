"""Application factory for creating Taskiq broker instances.

This module provides utilities for creating and configuring Taskiq brokers
with SQS support for dagster-taskiq.
"""

import os
import warnings
from typing import Any

from taskiq import AsyncBroker

from dagster_taskiq import defaults
from dagster_taskiq.broker import SqsBrokerConfig
from dagster_taskiq.cancellable_broker import CancellableSQSBroker


def _dict_from_source(config_source: Any) -> dict[str, Any]:
    """Extract a dictionary from a config source.

    Args:
        config_source: Configuration source (dict, object with __dict__, or None)

    Returns:
        Dictionary representation of the config source
    """
    if isinstance(config_source, dict):
        return config_source
    if config_source is None:
        return {}
    source_dict = getattr(config_source, "__dict__", {})
    return source_dict if isinstance(source_dict, dict) else {}


def _coerce_bool(value: Any) -> bool:
    """Coerce a value to a boolean.

    Args:
        value: Value to coerce (bool, str, or other)

    Returns:
        Boolean representation of the value
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return bool(value)


def _resolve_value(
    config: dict[str, Any],
    source_overrides: dict[str, Any],
    key: str,
    default: Any,
    *aliases: str,
) -> Any:
    """Resolve a configuration value from multiple sources.

    Args:
        config: Primary configuration dictionary
        source_overrides: Override configuration dictionary
        key: Primary key to search for
        default: Default value if key not found
        *aliases: Alternative keys to search for

    Returns:
        Resolved configuration value
    """
    search_keys = (key, *aliases)
    for container in (config, source_overrides):
        if not isinstance(container, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            continue
        for candidate in search_keys:
            if candidate in container and container[candidate] is not None:
                return container[candidate]
    return default


def make_app(app_args: dict[str, Any] | None = None) -> AsyncBroker:  # noqa: PLR0914
    """Create a taskiq broker with SQS backend and S3 result backend.

    Args:
        app_args: Optional configuration arguments for the broker

    Returns:
        Configured AsyncBroker instance
    """
    # Extract configuration from app_args or use defaults
    config = app_args or {}

    # Get SQS configuration
    queue_url = config.get("queue_url", defaults.sqs_queue_url)
    sqs_endpoint = config.get("endpoint_url", defaults.sqs_endpoint_url)
    region_name = config.get("region_name", defaults.aws_region_name)
    source_overrides = _dict_from_source(config.get("config_source"))

    # Get S3 configuration
    s3_bucket = _resolve_value(config, source_overrides, "s3_bucket_name", defaults.s3_bucket_name)
    s3_endpoint = _resolve_value(config, source_overrides, "s3_endpoint_url", defaults.s3_endpoint_url)

    # Get AWS credentials from environment or config
    aws_access_key_id = _resolve_value(config, source_overrides, "aws_access_key_id", os.getenv("AWS_ACCESS_KEY_ID"))
    aws_secret_access_key = config.get("aws_secret_access_key", os.getenv("AWS_SECRET_ACCESS_KEY"))

    # Get worker configuration
    max_messages_raw = _resolve_value(
        config, source_overrides, "max_number_of_messages", defaults.worker_max_messages, "worker_max_messages"
    )
    wait_time_raw = _resolve_value(config, source_overrides, "wait_time_seconds", defaults.wait_time_seconds)
    use_task_id_for_dedup = _resolve_value(config, source_overrides, "use_task_id_for_deduplication", False)  # noqa: FBT003
    extra_options_raw = _resolve_value(config, source_overrides, "extra_options", {}, "broker_transport_options")
    env_enable_cancellation = os.getenv("DAGSTER_TASKIQ_ENABLE_CANCELLATION")
    default_enable_cancellation: str | bool | None = env_enable_cancellation
    if default_enable_cancellation is None:
        # Disable cancellation by default until fully implemented (see IMPLEMENTATION_PROGRESS.md Phase 3)
        default_enable_cancellation = False
    enable_cancellation_raw = _resolve_value(
        config, source_overrides, "enable_cancellation", default_enable_cancellation
    )
    enable_cancellation = _coerce_bool(enable_cancellation_raw)

    # Create S3 result backend
    try:
        from taskiq_aio_sqs import S3Backend  # noqa: PLC0415

        result_backend: Any = S3Backend(
            bucket_name=s3_bucket,
            endpoint_url=s3_endpoint,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
    except ImportError:
        raise ImportError("taskiq-aio-sqs is required for S3 backend support") from None

    ignored_visibility = _resolve_value(config, source_overrides, "visibility_timeout", None)
    if ignored_visibility is not None:
        warnings.warn(
            '"visibility_timeout" is not supported by taskiq-aio-sqs; configure the SQS queue directly.',
            UserWarning,
            stacklevel=2,
        )

    # Determine fair-queue configuration. Taskiq fair queues require FIFO URLs.
    queue_is_fifo = str(queue_url or "").lower().endswith(".fifo")
    requested_fair_queue = _resolve_value(config, source_overrides, "is_fair_queue", None)

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

    try:
        max_messages = int(max_messages_raw)
    except (TypeError, ValueError):
        msg = f"invalid max_number_of_messages value: {max_messages_raw!r}"
        raise ValueError(msg) from None

    try:
        wait_time = int(wait_time_raw)
    except (TypeError, ValueError):
        msg = f"invalid wait_time_seconds value: {wait_time_raw!r}"
        raise ValueError(msg) from None

    extra_options = dict(extra_options_raw) if isinstance(extra_options_raw, dict) else {}

    broker_config = SqsBrokerConfig(
        queue_url=queue_url,
        endpoint_url=sqs_endpoint,
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        max_number_of_messages=max_messages,
        wait_time_seconds=wait_time,
        is_fair_queue=is_fair_queue,
        use_task_id_for_deduplication=_coerce_bool(use_task_id_for_dedup),
        s3_extended_bucket_name=s3_bucket,
        extra_options=extra_options,
    )

    if enable_cancellation:
        return CancellableSQSBroker(broker_config, result_backend=result_backend)

    return broker_config.create_broker(result_backend=result_backend)  # type: ignore[no-any-return]
