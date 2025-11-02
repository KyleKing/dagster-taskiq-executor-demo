"""Dagster ops for fast and slow async operations."""

import asyncio
import secrets
import time
from typing import Any

import structlog
from dagster import Config, OpExecutionContext, op
from pydantic import Field

logger = structlog.get_logger(__name__)

# Throughput thresholds for categorization
HIGH_THROUGHPUT_THRESHOLD = 100
MEDIUM_THROUGHPUT_THRESHOLD = 10


class FastOpConfig(Config):
    """Configuration for fast async operations."""

    base_duration: int = Field(default=20, description="Base duration in seconds")
    variance: int = Field(default=10, description="Duration variance in seconds")
    data_size: int = Field(default=1000, description="Size of data to process")
    sleep_interval: float = Field(
        default=1.0,
        ge=0.0,
        description="Seconds to sleep between progress updates",
    )


class SlowOpConfig(Config):
    """Configuration for slow async operations."""

    base_duration: int = Field(default=300, description="Base duration in seconds (5 minutes)")
    variance: int = Field(default=120, description="Duration variance in seconds (2 minutes)")
    data_size: int = Field(default=10000, description="Size of data to process")
    min_duration: int = Field(default=60, ge=1, description="Minimum total duration in seconds")
    sleep_interval: float = Field(
        default=1.0,
        ge=0.0,
        description="Seconds to sleep between progress updates",
    )


@op
async def fast_async_op(context: OpExecutionContext, config: FastOpConfig) -> dict[str, Any]:
    """Fast async operation that takes 20±10 seconds using asyncio.sleep.

    Args:
        context: Dagster operation execution context
        config: Configuration for the fast operation

    Returns:
        Dictionary containing operation results and metadata
    """
    # Calculate actual duration with variance
    variance = secrets.randbelow(2 * config.variance + 1) - config.variance
    duration = max(1, config.base_duration + variance)

    context.log.info("Starting fast async op with duration: %ss", duration)
    logger.info("fast_op_started", duration=duration, data_size=config.data_size)

    # Simulate async work with periodic progress updates
    start_time = asyncio.get_running_loop().time()
    progress_interval = max(1, duration // 3)  # Update progress 3 times during execution

    for i in range(duration):
        await asyncio.sleep(config.sleep_interval)
        if i % progress_interval == 0:
            progress = (i / duration) * 100
            context.log.info("Fast op progress: %.1f%%", progress)

    end_time = asyncio.get_running_loop().time()
    actual_duration = end_time - start_time

    result = {
        "op_type": "fast",
        "configured_duration": duration,
        "actual_duration": actual_duration,
        "data_processed": config.data_size,
        "items_per_second": config.data_size / actual_duration,
        "run_id": context.run_id,
        "op_name": context.op.name,
    }

    context.log.info("Fast async op completed in %.2fs", actual_duration)
    logger.info("fast_op_completed", **result)

    return result


@op
async def slow_async_op(context: OpExecutionContext, config: SlowOpConfig) -> dict[str, Any]:
    """Slow async operation that takes 5±2 minutes using asyncio.sleep.

    Args:
        context: Dagster operation execution context
        config: Configuration for the slow operation

    Returns:
        Dictionary containing operation results and metadata
    """
    # Calculate actual duration with variance
    variance = secrets.randbelow(2 * config.variance + 1) - config.variance
    duration = max(config.min_duration, config.base_duration + variance)

    context.log.info("Starting slow async op with duration: %ss (%.1f minutes)", duration, duration / 60)
    logger.info("slow_op_started", duration=duration, data_size=config.data_size)

    # Simulate async work with periodic progress updates
    start_time = asyncio.get_running_loop().time()
    progress_interval = max(10, duration // 10)  # Update progress 10 times during execution

    for i in range(duration):
        await asyncio.sleep(config.sleep_interval)
        if i % progress_interval == 0:
            progress = (i / duration) * 100
            context.log.info("Slow op progress: %.1f%%", progress)

    end_time = asyncio.get_running_loop().time()
    actual_duration = end_time - start_time

    result = {
        "op_type": "slow",
        "configured_duration": duration,
        "actual_duration": actual_duration,
        "data_processed": config.data_size,
        "items_per_second": config.data_size / actual_duration,
        "run_id": context.run_id,
        "op_name": context.op.name,
    }

    context.log.info("Slow async op completed in %.2fs (%.1f minutes)", actual_duration, actual_duration / 60)
    logger.info("slow_op_completed", **result)

    return result


@op
def data_processing_op(context: OpExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
    """Process data from upstream operations.

    Args:
        context: Dagster operation execution context
        input_data: Data from upstream operation

    Returns:
        Processed data with additional metadata
    """
    context.log.info("Processing data from %s operation", input_data.get("op_type", "unknown"))

    processed_data = {
        **input_data,
        "processed_at": time.time(),
        "processor_op": context.op.name,
        "processing_run_id": context.run_id,
    }

    # Add some processing metrics
    if "items_per_second" in input_data:
        processed_data["throughput_category"] = (
            "high"
            if input_data["items_per_second"] > HIGH_THROUGHPUT_THRESHOLD
            else "medium"
            if input_data["items_per_second"] > MEDIUM_THROUGHPUT_THRESHOLD
            else "low"
        )

    context.log.info("Data processing completed")
    logger.info("data_processing_completed", throughput_category=processed_data.get("throughput_category"))

    return processed_data


@op
def aggregation_op(
    context: OpExecutionContext, fast_result: dict[str, Any], slow_result: dict[str, Any]
) -> dict[str, Any]:
    """Aggregate results from multiple upstream operations.

    Args:
        context: Dagster operation execution context
        fast_result: Result from fast operation
        slow_result: Result from slow operation

    Returns:
        Aggregated results with summary statistics
    """
    context.log.info("Aggregating results from fast and slow operations")

    total_duration = fast_result["actual_duration"] + slow_result["actual_duration"]
    total_data = fast_result["data_processed"] + slow_result["data_processed"]

    aggregated_result = {
        "aggregation_type": "fast_slow_combined",
        "total_duration": total_duration,
        "total_data_processed": total_data,
        "average_throughput": total_data / total_duration,
        "fast_op_result": fast_result,
        "slow_op_result": slow_result,
        "run_id": context.run_id,
        "aggregated_at": time.time(),
    }

    context.log.info("Aggregation completed: %s items in %.2fs", total_data, total_duration)
    excluded_keys = {"fast_op_result", "slow_op_result"}
    logger.info(
        "aggregation_completed",
        **{k: v for k, v in aggregated_result.items() if k not in excluded_keys},
    )

    return aggregated_result
