"""Unit tests for priority/delay functionality without LocalStack."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dagster_taskiq.defaults import task_default_priority
from dagster_taskiq.executor import _priority_to_delay_seconds


def test_priority_to_delay_mapping():
    """Test that priority correctly maps to delay seconds."""
    # Default priority should have 0 delay
    assert _priority_to_delay_seconds(task_default_priority) == 0

    # Higher than default priority should have 0 delay
    assert _priority_to_delay_seconds(task_default_priority + 1) == 0
    assert _priority_to_delay_seconds(task_default_priority + 10) == 0

    # Lower priority should have increasing delay
    assert _priority_to_delay_seconds(task_default_priority - 1) == 10
    assert _priority_to_delay_seconds(task_default_priority - 2) == 20
    assert _priority_to_delay_seconds(task_default_priority - 5) == 50

    # Very low priority should be clamped to max delay
    assert _priority_to_delay_seconds(-100) == 900


def test_delay_label_passed_to_broker():
    """Test that delay labels are correctly passed to the taskiq broker."""
    import asyncio
    from dagster_taskiq.executor import _submit_task_async
    from dagster_taskiq.tasks import create_task

    async def run_test():

        # Create a mock broker
        mock_broker = MagicMock()
        mock_broker.startup = AsyncMock()
        mock_broker.result_backend = None

        # Create a mock task with kicker
        mock_task_result = MagicMock()
        mock_task_result.task_id = "test-task-id"

        mock_kiq = AsyncMock(return_value=mock_task_result)
        mock_kicker_with_labels = MagicMock()
        mock_kicker_with_labels.kiq = mock_kiq
        mock_kicker_with_labels.with_labels = MagicMock(return_value=mock_kicker_with_labels)

        mock_kicker = MagicMock(return_value=mock_kicker_with_labels)
        mock_task = MagicMock()
        mock_task.kicker = mock_kicker

        # Create a mock plan context
        mock_plan_context = MagicMock()
        mock_plan_context.reconstructable_job.get_python_origin.return_value = MagicMock()
        mock_plan_context.reconstructable_job.to_dict.return_value = {}
        mock_plan_context.dagster_run.run_id = "test-run-id"
        mock_plan_context.instance.get_ref.return_value = MagicMock()
        mock_plan_context.executor.retries.for_inner_plan.return_value = MagicMock()
        mock_plan_context.log = MagicMock()

        # Create a mock step
        mock_step = MagicMock()
        mock_step.key = "test_step"

        # Mock create_task to return our mock task
        with patch('dagster_taskiq.tasks.create_task', return_value=mock_task):
            # Test with high priority (should have low delay)
            result = await _submit_task_async(
                mock_broker,
                mock_plan_context,
                mock_step,
                "test-queue",
                priority=10,  # Higher than default (5), so delay should be 0
                known_state=None,
            )

            # Verify with_labels was called with delay=0
            mock_kicker_with_labels.with_labels.assert_called_once()
            call_kwargs = mock_kicker_with_labels.with_labels.call_args[1]
            assert call_kwargs['delay'] == 0, f"Expected delay=0 for priority=10, got delay={call_kwargs.get('delay')}"

            # Reset mocks
            mock_kicker_with_labels.with_labels.reset_mock()
            mock_kiq.reset_mock()

            # Test with low priority (should have high delay)
            result = await _submit_task_async(
                mock_broker,
                mock_plan_context,
                mock_step,
                "test-queue",
                priority=-3,  # Much lower than default (5), so delay should be (5 - (-3)) * 10 = 80
                known_state=None,
            )

            # Verify with_labels was called with delay=80
            mock_kicker_with_labels.with_labels.assert_called_once()
            call_kwargs = mock_kicker_with_labels.with_labels.call_args[1]
            assert call_kwargs['delay'] == 80, f"Expected delay=80 for priority=-3, got delay={call_kwargs.get('delay')}"

    asyncio.run(run_test())
