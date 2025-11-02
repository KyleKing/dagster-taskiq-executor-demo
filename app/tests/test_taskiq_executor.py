"""Tests for TaskIQ executor."""

import pytest
from unittest.mock import Mock, patch

from dagster import DagsterEventType

from dagster_taskiq.config.settings import Settings
from dagster_taskiq.taskiq_executor import TaskIQExecutor
from dagster_taskiq.taskiq_executor.task_payloads import TaskState


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    return Settings(
        taskiq_queue_name="test-queue.fifo",
        taskiq_visibility_timeout=300,
    )


@patch('dagster_taskiq.taskiq_executor.get_idempotency_storage')
@patch('dagster_taskiq.taskiq_executor.LocalStackSqsBroker')
def test_executor_initialization(mock_broker_class: Mock, mock_storage_func: Mock, mock_settings: Settings) -> None:
    """Test executor initialization."""
    mock_broker = Mock()
    mock_broker_class.return_value = mock_broker
    mock_storage = Mock()
    mock_storage_func.return_value = mock_storage

    executor = TaskIQExecutor(mock_settings)
    assert executor.settings == mock_settings
    assert executor.pending_steps == {}
    mock_broker_class.assert_called_once_with(mock_settings)
    mock_storage_func.assert_called_once()


@patch('dagster_taskiq.taskiq_executor.get_idempotency_storage')
@patch('dagster_taskiq.taskiq_executor.LocalStackSqsBroker')
def test_executor_skips_completed_steps(mock_broker_class: Mock, mock_storage_func: Mock, mock_settings: Settings) -> None:
    """Test that executor skips already completed steps."""
    mock_broker = Mock()
    mock_broker_class.return_value = mock_broker
    mock_storage = Mock()
    mock_storage.is_completed.return_value = True
    mock_storage_func.return_value = mock_storage

    executor = TaskIQExecutor(mock_settings)

    # Mock plan context and step
    plan_context = Mock()
    plan_context.run_id = "test-run"
    plan_context.for_step.return_value = Mock()

    step = Mock()
    step.key = "test-step"
    step.kind = "COMPUTE"

    # Execute
    events = list(executor._submit_step(plan_context, step))

    # Should yield success event for completed step
    assert len(events) == 2  # start and success events
    assert events[0].event_type == DagsterEventType.STEP_START
    assert events[1].event_type == DagsterEventType.STEP_SUCCESS
    mock_storage.is_completed.assert_called_once_with("test-run:test-step")


@patch('dagster_taskiq.taskiq_executor.get_idempotency_storage')
@patch('dagster_taskiq.taskiq_executor.LocalStackSqsBroker')
def test_executor_submits_new_steps(mock_broker_class: Mock, mock_storage_func: Mock, mock_settings: Settings) -> None:
    """Test that executor submits new steps to TaskIQ."""
    mock_broker = Mock()
    mock_broker_class.return_value = mock_broker
    mock_storage = Mock()
    mock_storage.is_completed.return_value = False
    mock_storage_func.return_value = mock_storage

    executor = TaskIQExecutor(mock_settings)

    # Mock plan context and step
    plan_context = Mock()
    plan_context.run_id = "test-run"
    plan_context.for_step.return_value = Mock()

    step = Mock()
    step.key = "test-step"
    step.kind = "COMPUTE"
    step.op_def.name = "test_op"
    step.op_config = {}

    # Execute
    events = list(executor._submit_step(plan_context, step))

    # Should yield start event and submit to broker
    assert len(events) == 1
    assert events[0].event_type == DagsterEventType.STEP_START
    mock_broker.kick_sync.assert_called_once()
    mock_storage.save_record.assert_called_once()
    mock_storage.update_state.assert_called_once_with("test-run:test-step", TaskState.RUNNING)