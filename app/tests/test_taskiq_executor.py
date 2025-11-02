"""Tests for TaskIQ executor."""

from unittest.mock import Mock, patch

import pytest
from dagster import DagsterEventType

from dagster_taskiq.config.settings import Settings
from dagster_taskiq.taskiq_executor import TaskIQExecutor
from dagster_taskiq.taskiq_executor.task_payloads import TaskState


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    settings = Settings()
    settings.taskiq_queue_name = "test-queue.fifo"
    settings.taskiq_visibility_timeout = 300
    return settings


@patch("dagster_taskiq.taskiq_executor.get_idempotency_storage")
@patch("dagster_taskiq.taskiq_executor.LocalStackSqsBroker")
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


@patch("dagster_taskiq.taskiq_executor.get_idempotency_storage")
@patch("dagster_taskiq.taskiq_executor.LocalStackSqsBroker")
@patch("dagster_taskiq.taskiq_executor.DagsterEvent")
def test_executor_skips_completed_steps(
    mock_event_class: Mock, mock_broker_class: Mock, mock_storage_func: Mock, mock_settings: Settings
) -> None:
    """Test that executor skips already completed steps."""
    mock_broker = Mock()
    mock_broker_class.return_value = mock_broker
    mock_storage = Mock()
    mock_storage.is_completed.return_value = True
    mock_storage_func.return_value = mock_storage

    # Mock Dagster events
    mock_start_event = Mock()
    mock_start_event.event_type = DagsterEventType.STEP_START
    mock_success_event = Mock()
    mock_success_event.event_type = DagsterEventType.STEP_SUCCESS
    mock_event_class.step_start_event.return_value = mock_start_event
    mock_event_class.step_success_event.return_value = mock_success_event

    executor = TaskIQExecutor(mock_settings)

    # Mock plan context and step
    plan_context = Mock()
    plan_context.run_id = "test-run"
    plan_context.for_step.return_value = Mock()

    step = Mock()
    step.key = "test-step"
    step.kind = "COMPUTE"

    # Execute
    events = list(executor._submit_step(plan_context, step))  # type: ignore[attr-defined]

    # Should yield success event for completed step
    assert len(events) == 1  # only success event for completed steps
    assert events[0].event_type == DagsterEventType.STEP_SUCCESS
    mock_storage.is_completed.assert_called_once_with("test-run:test-step")


@patch("dagster_taskiq.taskiq_executor.get_idempotency_storage")
@patch("dagster_taskiq.taskiq_executor.LocalStackSqsBroker")
@patch("dagster_taskiq.taskiq_executor.DagsterEvent")
def test_executor_submits_new_steps(
    mock_event_class: Mock, mock_broker_class: Mock, mock_storage_func: Mock, mock_settings: Settings
) -> None:
    """Test that executor submits new steps to TaskIQ."""
    mock_broker = Mock()
    mock_broker_class.return_value = mock_broker
    mock_storage = Mock()
    mock_storage.is_completed.return_value = False
    mock_storage_func.return_value = mock_storage

    # Mock Dagster events
    mock_start_event = Mock()
    mock_start_event.event_type = DagsterEventType.STEP_START
    mock_event_class.step_start_event.return_value = mock_start_event

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
    events = list(executor._submit_step(plan_context, step))  # type: ignore[attr-defined]

    # Should yield start event and submit to broker
    assert len(events) == 1
    assert events[0].event_type == DagsterEventType.STEP_START
    mock_broker.kick_sync.assert_called_once()
    mock_storage.save_record.assert_called_once()
    mock_storage.update_state.assert_called_once_with("test-run:test-step", TaskState.RUNNING)


@patch("dagster_taskiq.taskiq_executor.get_idempotency_storage")
@patch("dagster_taskiq.taskiq_executor.LocalStackSqsBroker")
@patch("dagster_taskiq.taskiq_executor.DagsterEvent")
def test_executor_handles_submission_failure(
    mock_event_class: Mock, mock_broker_class: Mock, mock_storage_func: Mock, mock_settings: Settings
) -> None:
    """Test that executor handles submission failures."""
    mock_broker = Mock()
    mock_broker.kick_sync.side_effect = Exception("Broker error")
    mock_broker_class.return_value = mock_broker
    mock_storage = Mock()
    mock_storage.is_completed.return_value = False
    mock_storage_func.return_value = mock_storage

    # Mock Dagster events
    mock_failure_event = Mock()
    mock_failure_event.event_type = DagsterEventType.STEP_FAILURE
    mock_event_class.step_failure_event.return_value = mock_failure_event

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
    events = list(executor._submit_step(plan_context, step))  # type: ignore[attr-defined]

    # Should yield failure event
    assert len(events) == 1
    assert events[0].event_type == DagsterEventType.STEP_FAILURE
    mock_storage.update_state.assert_called_once_with("test-run:test-step", TaskState.FAILED, "Broker error")
