import os
import warnings
from typing import Any, Optional

from taskiq import AsyncBroker

from dagster_taskiq.broker import SqsBrokerConfig
from dagster_taskiq.defaults import (
    aws_region_name,
    sqs_endpoint_url,
    sqs_queue_url,
    s3_bucket_name,
    s3_endpoint_url,
    wait_time_seconds,
    worker_max_messages,
)


def _dict_from_source(config_source: Any) -> dict[str, Any]:
    if isinstance(config_source, dict):
        return config_source
    if config_source is None:
        return {}
    source_dict = getattr(config_source, '__dict__', {})
    return source_dict if isinstance(source_dict, dict) else {}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 't', 'yes', 'y', 'on'}
    return bool(value)


def _resolve_value(
    config: dict[str, Any],
    source_overrides: dict[str, Any],
    key: str,
    default: Any,
    *aliases: str,
) -> Any:
    search_keys = (key,) + aliases
    for container in (config, source_overrides):
        if not isinstance(container, dict):
            continue
        for candidate in search_keys:
            if candidate in container and container[candidate] is not None:
                return container[candidate]
    return default


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
    source_overrides = _dict_from_source(config.get('config_source'))

    # Get S3 configuration
    s3_bucket = _resolve_value(config, source_overrides, 's3_bucket_name', s3_bucket_name)
    s3_endpoint = _resolve_value(config, source_overrides, 's3_endpoint_url', s3_endpoint_url)

    # Get AWS credentials from environment or config
    aws_access_key_id = _resolve_value(
        config, source_overrides, 'aws_access_key_id', os.getenv('AWS_ACCESS_KEY_ID')
    )
    aws_secret_access_key = config.get(
        'aws_secret_access_key', os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    # Get worker configuration
    max_messages_raw = _resolve_value(
        config, source_overrides, 'max_number_of_messages', worker_max_messages, 'worker_max_messages'
    )
    wait_time_raw = _resolve_value(
        config, source_overrides, 'wait_time_seconds', wait_time_seconds
    )
    delay_seconds_raw = _resolve_value(config, source_overrides, 'delay_seconds', 0)
    use_task_id_for_dedup = _resolve_value(
        config, source_overrides, 'use_task_id_for_deduplication', False
    )
    extra_options_raw = _resolve_value(
        config, source_overrides, 'extra_options', {}, 'broker_transport_options'
    )

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

    ignored_visibility = _resolve_value(config, source_overrides, 'visibility_timeout', None)
    if ignored_visibility is not None:
        warnings.warn(
            '"visibility_timeout" is not supported by taskiq-aio-sqs; configure the SQS queue directly.',
            UserWarning,
            stacklevel=2,
        )

    # Determine fair-queue configuration. Taskiq fair queues require FIFO URLs.
    queue_is_fifo = str(queue_url or "").lower().endswith(".fifo")
    requested_fair_queue = _resolve_value(config, source_overrides, 'is_fair_queue', None)

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
        raise ValueError(f'invalid max_number_of_messages value: {max_messages_raw!r}')

    try:
        wait_time = int(wait_time_raw)
    except (TypeError, ValueError):
        raise ValueError(f'invalid wait_time_seconds value: {wait_time_raw!r}')

    try:
        delay_seconds = int(delay_seconds_raw)
    except (TypeError, ValueError):
        raise ValueError(f'invalid delay_seconds value: {delay_seconds_raw!r}')

    extra_options = dict(extra_options_raw) if isinstance(extra_options_raw, dict) else {}

    broker_config = SqsBrokerConfig(
        queue_url=queue_url,
        endpoint_url=sqs_endpoint,
        region_name=region_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        max_number_of_messages=max_messages,
        wait_time_seconds=wait_time,
        delay_seconds=delay_seconds,
        is_fair_queue=is_fair_queue,
        use_task_id_for_deduplication=_coerce_bool(use_task_id_for_dedup),
        s3_extended_bucket_name=s3_bucket,
        extra_options=extra_options,
    )

    return broker_config.create_broker(result_backend=result_backend)
