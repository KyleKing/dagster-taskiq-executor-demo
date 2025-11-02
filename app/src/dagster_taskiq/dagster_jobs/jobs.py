"""Dagster job definitions for fast and slow operations."""

from __future__ import annotations

from dagster import job

from .ops import aggregation_op, data_processing_op, fast_async_op, slow_async_op


@job(
    name="fast_job",
    description="Job with fast async operations (20±10 seconds)",
)
def fast_job() -> None:
    """Job that executes fast async operations."""
    fast_result = fast_async_op()
    data_processing_op(fast_result)


@job(
    name="slow_job",
    description="Job with slow async operations (5±2 minutes)",
)
def slow_job() -> None:
    """Job that executes slow async operations."""
    slow_result = slow_async_op()
    data_processing_op(slow_result)


@job(
    name="mixed_job",
    description="Job with both fast and slow operations",
)
def mixed_job() -> None:
    """Job that executes both fast and slow operations and aggregates results."""
    fast_result = fast_async_op()
    slow_result = slow_async_op()

    # Process results independently
    processed_fast = data_processing_op(fast_result)
    processed_slow = data_processing_op(slow_result)

    # Aggregate the processed results
    aggregation_op(processed_fast, processed_slow)


@job(
    name="parallel_fast_job",
    description="Job with multiple parallel fast operations",
)
def parallel_fast_job() -> None:
    """Job that executes multiple fast operations in parallel."""
    # Create multiple fast operations that can run in parallel
    fast_result_1 = fast_async_op.alias("fast_op_1")()
    fast_result_2 = fast_async_op.alias("fast_op_2")()
    fast_result_3 = fast_async_op.alias("fast_op_3")()

    # Process each result
    data_processing_op.alias("process_1")(fast_result_1)
    data_processing_op.alias("process_2")(fast_result_2)
    data_processing_op.alias("process_3")(fast_result_3)


@job(
    name="sequential_slow_job",
    description="Job with sequential slow operations",
)
def sequential_slow_job() -> None:
    """Job that executes slow operations sequentially."""
    # First slow operation
    slow_result_1 = slow_async_op.alias("slow_op_1")()
    processed_1 = data_processing_op.alias("process_1")(slow_result_1)

    # Second slow operation (depends on first)
    slow_result_2 = slow_async_op.alias("slow_op_2")()
    processed_2 = data_processing_op.alias("process_2")(slow_result_2)

    # Aggregate both results
    aggregation_op(processed_1, processed_2)
