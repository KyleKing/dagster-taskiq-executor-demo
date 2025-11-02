"""Tests for auto-scaler service."""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from dagster_taskiq_demo.auto_scaler import AutoScalerService, QueueMetrics, ScalingDecision
from dagster_taskiq_demo.config.settings import Settings


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    settings = Settings()
    settings.ecs_cluster_name = "test-cluster"
    settings.ecs_worker_service_name = "test-workers"
    settings.autoscaler_min_workers = 2
    settings.autoscaler_max_workers = 10
    settings.autoscaler_scale_up_threshold = 5
    settings.autoscaler_scale_down_threshold = 2
    settings.autoscaler_cooldown_seconds = 60
    return settings


@pytest.fixture
def auto_scaler_service(mock_settings: Settings) -> AutoScalerService:
    """Create auto-scaler service instance."""
    service = AutoScalerService.__new__(AutoScalerService)
    service.settings = mock_settings
    service.logger = Mock()
    service.running = False
    service.health_server = None
    service.last_scale_time = 0.0
    service.current_worker_count = mock_settings.autoscaler_min_workers
    service.sqs_client = AsyncMock()
    service.ecs_client = AsyncMock()
    return service


class TestQueueMetrics:
    """Test queue metrics functionality."""

    @pytest.mark.asyncio
    async def test_get_queue_metrics_success(self, auto_scaler_service: AutoScalerService) -> None:
        """Test successful queue metrics retrieval."""
        mock_response = {
            "Attributes": {
                "ApproximateNumberOfMessages": "10",
                "ApproximateNumberOfMessagesNotVisible": "3",
                "ApproximateAgeOfOldestMessage": "120",
            }
        }
        auto_scaler_service.sqs_client.get_queue_attributes = AsyncMock(return_value=mock_response)

        metrics = await auto_scaler_service.get_queue_metrics()

        assert metrics.visible_messages == 10
        assert metrics.not_visible_messages == 3
        assert metrics.oldest_message_age_seconds == 120
        assert isinstance(metrics.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_get_queue_metrics_error(self, auto_scaler_service: AutoScalerService) -> None:
        """Test queue metrics retrieval with error."""
        auto_scaler_service.sqs_client.get_queue_attributes = AsyncMock(side_effect=Exception("SQS error"))

        metrics = await auto_scaler_service.get_queue_metrics()

        assert metrics.visible_messages == 0
        assert metrics.not_visible_messages == 0
        assert metrics.oldest_message_age_seconds is None


class TestScalingDecision:
    """Test scaling decision logic."""

    def test_calculate_scaling_decision_scale_up(self, auto_scaler_service: AutoScalerService) -> None:
        """Test scale up decision."""
        auto_scaler_service.current_worker_count = 2
        metrics = QueueMetrics(12, 0, None, datetime.now(UTC))  # 12 > 2*5 = 10

        decision = auto_scaler_service.calculate_scaling_decision(metrics)

        assert decision.action == "scale_up"
        assert decision.target_count == 3  # 2 + 1
        assert "visible messages (12)" in decision.reason

    def test_calculate_scaling_decision_scale_down(self, auto_scaler_service: AutoScalerService) -> None:
        """Test scale down decision."""
        auto_scaler_service.current_worker_count = 4
        metrics = QueueMetrics(6, 0, None, datetime.now(UTC))  # 6 < 4*2 = 8

        decision = auto_scaler_service.calculate_scaling_decision(metrics)

        assert decision.action == "scale_down"
        assert decision.target_count == 3  # 4 - 1
        assert "visible messages (6)" in decision.reason

    def test_calculate_scaling_decision_no_action_within_thresholds(
        self, auto_scaler_service: AutoScalerService
    ) -> None:
        """Test no action when within thresholds."""
        auto_scaler_service.current_worker_count = 4
        metrics = QueueMetrics(15, 0, None, datetime.now(UTC))  # 15 > 4*2=8, < 4*5=20

        decision = auto_scaler_service.calculate_scaling_decision(metrics)

        assert decision.action == "no_action"
        assert decision.target_count == 4

    def test_calculate_scaling_decision_cooldown(self, auto_scaler_service: AutoScalerService) -> None:
        """Test cooldown prevents scaling."""
        auto_scaler_service.current_worker_count = 2
        auto_scaler_service.last_scale_time = time.time()  # Current time
        metrics = QueueMetrics(12, 0, None, datetime.now(UTC))

        decision = auto_scaler_service.calculate_scaling_decision(metrics)

        assert decision.action == "no_action"
        assert "cooldown active" in decision.reason

    def test_calculate_scaling_decision_respects_min_workers(self, auto_scaler_service: AutoScalerService) -> None:
        """Test scale down respects minimum workers."""
        auto_scaler_service.current_worker_count = 2  # Already at minimum
        metrics = QueueMetrics(2, 0, None, datetime.now(UTC))

        decision = auto_scaler_service.calculate_scaling_decision(metrics)

        assert decision.action == "no_action"
        assert decision.target_count == 2

    def test_calculate_scaling_decision_respects_max_workers(self, auto_scaler_service: AutoScalerService) -> None:
        """Test scale up respects maximum workers."""
        auto_scaler_service.current_worker_count = 10  # Already at maximum
        metrics = QueueMetrics(100, 0, None, datetime.now(UTC))

        decision = auto_scaler_service.calculate_scaling_decision(metrics)

        assert decision.action == "no_action"
        assert decision.target_count == 10


class TestScalingExecution:
    """Test scaling action execution."""

    @pytest.mark.asyncio
    async def test_execute_scaling_action_scale_up(self, auto_scaler_service: AutoScalerService) -> None:
        """Test executing scale up action."""
        auto_scaler_service.ecs_client.update_service = AsyncMock()
        decision = ScalingDecision("scale_up", 5, "test")

        await auto_scaler_service.execute_scaling_action(decision)

        auto_scaler_service.ecs_client.update_service.assert_called_once_with(
            cluster="test-cluster",
            service="test-workers",
            desiredCount=5,
        )
        assert auto_scaler_service.current_worker_count == 5

    @pytest.mark.asyncio
    async def test_execute_scaling_action_no_action(self, auto_scaler_service: AutoScalerService) -> None:
        """Test no action doesn't call ECS."""
        auto_scaler_service.ecs_client.update_service = AsyncMock()
        decision = ScalingDecision("no_action", 3, "test")

        await auto_scaler_service.execute_scaling_action(decision)

        auto_scaler_service.ecs_client.update_service.assert_not_called()


class TestFailureSimulation:
    """Test failure simulation functionality."""

    @pytest.mark.asyncio
    async def test_simulate_worker_crash(self, auto_scaler_service: AutoScalerService) -> None:
        """Test worker crash simulation."""
        mock_response = {"taskArns": ["arn:aws:ecs:us-east-1:123456789012:task/cluster/task1"]}
        auto_scaler_service.ecs_client.list_tasks = AsyncMock(return_value=mock_response)
        auto_scaler_service.ecs_client.stop_task = AsyncMock()

        await auto_scaler_service.simulate_worker_crash()

        auto_scaler_service.ecs_client.stop_task.assert_called_once_with(
            cluster="test-cluster",
            task="arn:aws:ecs:us-east-1:123456789012:task/cluster/task1",
            reason="Simulated failure for testing",
        )

    @pytest.mark.asyncio
    async def test_simulate_drain_and_restart(self, auto_scaler_service: AutoScalerService) -> None:
        """Test drain and restart simulation."""
        auto_scaler_service.ecs_client.update_service = AsyncMock()

        with patch("asyncio.sleep", AsyncMock()):
            await auto_scaler_service.simulate_drain_and_restart()

        # Should scale to 0, wait, then scale back to min
        assert auto_scaler_service.ecs_client.update_service.call_count == 2
        calls = auto_scaler_service.ecs_client.update_service.call_args_list

        # First call: scale to 0
        assert calls[0][1]["desiredCount"] == 0
        # Second call: scale to min
        assert calls[1][1]["desiredCount"] == 2

        assert auto_scaler_service.current_worker_count == 2

    @pytest.mark.asyncio
    async def test_simulate_network_partition(self, auto_scaler_service: AutoScalerService) -> None:
        """Test network partition simulation."""
        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            await auto_scaler_service.simulate_network_partition()

        mock_sleep.assert_called_once_with(60)


class TestMetricsEmission:
    """Test metrics emission."""

    def test_emit_metrics(self, auto_scaler_service: AutoScalerService) -> None:
        """Test metrics emission."""
        auto_scaler_service.current_worker_count = 3
        metrics = QueueMetrics(5, 2, 150, datetime.now(UTC))

        auto_scaler_service._emit_metrics(metrics)

        # Check that metrics log was called on the mock logger
        auto_scaler_service.logger.info.assert_called()
        call_args = auto_scaler_service.logger.info.call_args
        format_str = call_args[0][0]
        values = call_args[0][1:]
        assert "METRICS" in format_str
        assert 5 in values  # queue_depth_visible
        assert 3 in values  # current_workers

    def test_emit_metrics_alert_on_old_messages(self, auto_scaler_service: AutoScalerService) -> None:
        """Test alert emission for old messages."""
        metrics = QueueMetrics(1, 0, 350, datetime.now(UTC))  # Over 5 minutes

        auto_scaler_service._emit_metrics(metrics)

        auto_scaler_service.logger.warning.assert_called_once()
        call_args = auto_scaler_service.logger.warning.call_args
        format_str = call_args[0][0]
        values = call_args[0][1:]
        assert "ALERT" in format_str
        assert 350 in values
