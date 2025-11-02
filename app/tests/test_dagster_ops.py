"""Tests for Dagster operations."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import Mock

import pytest
from dagster import OpExecutionContext

from dagster_taskiq.dagster_jobs.ops import (
    FastOpConfig,
    SlowOpConfig,
    aggregation_op,
    data_processing_op,
    fast_async_op,
    slow_async_op,
)


class TestFastAsyncOp:
    """Test fast async operation."""

    async def test_fast_async_op_default_config(self, mock_op_context: OpExecutionContext, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time):
        """Test fast async op with default configuration."""
        config = FastOpConfig()
        
        result = await fast_async_op(mock_op_context, config)
        
        assert result["op_type"] == "fast"
        assert result["configured_duration"] == 20  # base duration with 0 variance
        assert result["actual_duration"] == 20.0
        assert result["data_processed"] == 1000
        assert result["items_per_second"] == 50.0  # 1000 / 20
        assert result["run_id"] == mock_op_context.run_id
        assert result["op_name"] == mock_op_context.op.name

    async def test_fast_async_op_custom_config(self, mock_op_context: OpExecutionContext, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time):
        """Test fast async op with custom configuration."""
        config = FastOpConfig(base_duration=10, variance=5, data_size=500)
        
        result = await fast_async_op(mock_op_context, config)
        
        assert result["op_type"] == "fast"
        assert result["configured_duration"] == 10  # base duration with 0 variance
        assert result["data_processed"] == 500
        assert result["items_per_second"] == 25.0  # 500 / 20 (mocked actual duration)

    @pytest.mark.parametrize(
        ("base_duration", "variance", "expected_min_duration"),
        [
            (1, 5, 1),  # Should not go below 1
            (0, 10, 1),  # Should not go below 1
            (5, 10, 1),  # With max negative variance, should not go below 1
        ],
    )
    async def test_fast_async_op_minimum_duration(self, mock_op_context: OpExecutionContext, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time, base_duration: int, variance: int, expected_min_duration: int):
        """Test that fast async op respects minimum duration."""
        # Mock randbelow to return maximum negative variance
        mock_secrets_randbelow.return_value = 0  # This gives -variance when subtracted
        
        config = FastOpConfig(base_duration=base_duration, variance=variance)
        
        result = await fast_async_op(mock_op_context, config)
        
        assert result["configured_duration"] >= expected_min_duration


class TestSlowAsyncOp:
    """Test slow async operation."""

    async def test_slow_async_op_default_config(self, mock_op_context: OpExecutionContext, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time):
        """Test slow async op with default configuration."""
        config = SlowOpConfig()
        
        result = await slow_async_op(mock_op_context, config)
        
        assert result["op_type"] == "slow"
        assert result["configured_duration"] == 300  # base duration with 0 variance
        assert result["actual_duration"] == 20.0  # mocked duration
        assert result["data_processed"] == 10000
        assert result["items_per_second"] == 500.0  # 10000 / 20
        assert result["run_id"] == mock_op_context.run_id
        assert result["op_name"] == mock_op_context.op.name

    async def test_slow_async_op_custom_config(self, mock_op_context: OpExecutionContext, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time):
        """Test slow async op with custom configuration."""
        config = SlowOpConfig(base_duration=180, variance=60, data_size=5000)
        
        result = await slow_async_op(mock_op_context, config)
        
        assert result["op_type"] == "slow"
        assert result["configured_duration"] == 180  # base duration with 0 variance
        assert result["data_processed"] == 5000
        assert result["items_per_second"] == 250.0  # 5000 / 20 (mocked actual duration)

    @pytest.mark.parametrize(
        ("base_duration", "variance", "expected_min_duration"),
        [
            (30, 60, 60),  # Should not go below 60
            (120, 180, 60),  # Should not go below 60
            (600, 120, 480),  # Normal case: 600 - 120 = 480
        ],
    )
    async def test_slow_async_op_minimum_duration(self, mock_op_context: OpExecutionContext, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time, base_duration: int, variance: int, expected_min_duration: int):
        """Test that slow async op respects minimum duration of 60 seconds."""
        # Mock randbelow to return maximum negative variance
        mock_secrets_randbelow.return_value = 0  # This gives -variance when subtracted
        
        config = SlowOpConfig(base_duration=base_duration, variance=variance)
        
        result = await slow_async_op(mock_op_context, config)
        
        assert result["configured_duration"] >= 60  # Minimum is 60 seconds


class TestDataProcessingOp:
    """Test data processing operation."""

    def test_data_processing_op_fast_input(self, mock_op_context: OpExecutionContext, mock_loop_time):
        """Test data processing op with fast operation input."""
        input_data = {
            "op_type": "fast",
            "configured_duration": 20,
            "actual_duration": 18.5,
            "data_processed": 1000,
            "items_per_second": 54.05,  # High throughput
            "run_id": "test-run-123",
            "op_name": "fast_async_op",
        }
        
        result = data_processing_op(mock_op_context, input_data)
        
        assert result["op_type"] == "fast"
        assert result["processed_at"] == 1000.0  # mocked time
        assert result["processor_op"] == mock_op_context.op.name
        assert result["processing_run_id"] == mock_op_context.run_id
        assert result["throughput_category"] == "high"  # > 100 threshold

    def test_data_processing_op_slow_input(self, mock_op_context: OpExecutionContext, mock_loop_time):
        """Test data processing op with slow operation input."""
        input_data = {
            "op_type": "slow",
            "configured_duration": 300,
            "actual_duration": 285.2,
            "data_processed": 10000,
            "items_per_second": 35.06,  # Medium throughput
            "run_id": "test-run-456",
            "op_name": "slow_async_op",
        }
        
        result = data_processing_op(mock_op_context, input_data)
        
        assert result["op_type"] == "slow"
        assert result["processed_at"] == 1000.0  # mocked time
        assert result["processor_op"] == mock_op_context.op.name
        assert result["processing_run_id"] == mock_op_context.run_id
        assert result["throughput_category"] == "medium"  # 10 < x <= 100

    @pytest.mark.parametrize(
        ("items_per_second", "expected_category"),
        [
            (150.0, "high"),    # > 100
            (50.0, "medium"),   # 10 < x <= 100
            (5.0, "low"),       # <= 10
            (100.1, "high"),    # Edge case: just above high threshold
            (10.0, "medium"),   # Edge case: exactly at medium threshold
            (0.5, "low"),       # Very low throughput
        ],
    )
    def test_data_processing_op_throughput_categories(self, mock_op_context: OpExecutionContext, mock_loop_time, items_per_second: float, expected_category: str):
        """Test throughput categorization logic."""
        input_data = {
            "op_type": "test",
            "items_per_second": items_per_second,
        }
        
        result = data_processing_op(mock_op_context, input_data)
        
        assert result["throughput_category"] == expected_category

    def test_data_processing_op_missing_throughput(self, mock_op_context: OpExecutionContext, mock_loop_time):
        """Test data processing op with missing throughput data."""
        input_data = {
            "op_type": "unknown",
            "some_other_field": "value",
        }
        
        result = data_processing_op(mock_op_context, input_data)
        
        assert "throughput_category" not in result
        assert result["op_type"] == "unknown"
        assert result["processed_at"] == 1000.0


class TestAggregationOp:
    """Test aggregation operation."""

    def test_aggregation_op_basic(self, mock_op_context: OpExecutionContext, mock_loop_time):
        """Test basic aggregation of fast and slow results."""
        fast_result = {
            "op_type": "fast",
            "actual_duration": 18.5,
            "data_processed": 1000,
            "items_per_second": 54.05,
        }
        
        slow_result = {
            "op_type": "slow",
            "actual_duration": 285.2,
            "data_processed": 10000,
            "items_per_second": 35.06,
        }
        
        result = aggregation_op(mock_op_context, fast_result, slow_result)
        
        assert result["aggregation_type"] == "fast_slow_combined"
        assert result["total_duration"] == 303.7  # 18.5 + 285.2
        assert result["total_data_processed"] == 11000  # 1000 + 10000
        assert abs(result["average_throughput"] - 36.21) < 0.01  # 11000 / 303.7
        assert result["run_id"] == mock_op_context.run_id
        assert result["aggregated_at"] == 1000.0
        assert result["fast_op_result"] == fast_result
        assert result["slow_op_result"] == slow_result

    def test_aggregation_op_edge_cases(self, mock_op_context: OpExecutionContext, mock_loop_time):
        """Test aggregation with edge case values."""
        fast_result = {
            "actual_duration": 0.1,  # Very fast
            "data_processed": 1,     # Minimal data
        }
        
        slow_result = {
            "actual_duration": 1000.0,  # Very slow
            "data_processed": 1000000,  # Large data
        }
        
        result = aggregation_op(mock_op_context, fast_result, slow_result)
        
        assert result["total_duration"] == 1000.1
        assert result["total_data_processed"] == 1000001
        assert abs(result["average_throughput"] - 999.9) < 0.1  # ~1000001 / 1000.1