"""Tests for the load simulator."""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from dagster_taskiq_demo.load_simulator.cli import cli
from dagster_taskiq_demo.load_simulator.simulator import LoadSimulator


class TestLoadSimulator:
    """Test the LoadSimulator class."""

    @pytest.fixture
    def simulator(self) -> LoadSimulator:
        """Create a LoadSimulator instance for testing."""
        return LoadSimulator(host="localhost", port=3000)

    def test_init(self, simulator: LoadSimulator) -> None:
        """Test LoadSimulator initialization."""
        assert simulator.client is not None
        assert simulator.repository_location_name is None
        assert simulator.repository_name is None

    @patch("dagster_taskiq_demo.load_simulator.simulator.DagsterGraphQLClient")
    def test_submit_run_success(self, mock_client_class: Mock, simulator: LoadSimulator) -> None:
        """Test successful run submission."""
        mock_client = Mock()
        mock_client.submit_job_execution.return_value = "test-run-id"
        mock_client_class.return_value = mock_client

        # Re-initialize simulator with mocked client
        simulator.client = mock_client

        result = simulator.submit_run("test_job")

        assert result == "test-run-id"
        mock_client.submit_job_execution.assert_called_once_with(
            job_name="test_job",
            run_config={},
            tags={"load_simulator": "true", "submitted_at": pytest.any},
        )

    @patch("dagster_taskiq_demo.load_simulator.simulator.DagsterGraphQLClient")
    def test_submit_run_with_repo_params(self, mock_client_class: Mock) -> None:
        """Test run submission with repository parameters."""
        mock_client = Mock()
        mock_client.submit_job_execution.return_value = "test-run-id"
        mock_client_class.return_value = mock_client

        simulator = LoadSimulator(
            host="localhost",
            port=3000,
            repository_location_name="test_location",
            repository_name="test_repo",
        )
        simulator.client = mock_client

        result = simulator.submit_run("test_job")

        assert result == "test-run-id"
        mock_client.submit_job_execution.assert_called_once_with(
            job_name="test_job",
            repository_location_name="test_location",
            repository_name="test_repo",
            run_config={},
            tags={"load_simulator": "true", "submitted_at": pytest.any},
        )

    @patch("dagster_taskiq_demo.load_simulator.simulator.DagsterGraphQLClient")
    def test_submit_run_failure(self, mock_client_class: Mock, simulator: LoadSimulator) -> None:
        """Test run submission failure."""
        from dagster_graphql import DagsterGraphQLClientError

        mock_client = Mock()
        mock_client.submit_job_execution.side_effect = DagsterGraphQLClientError("Test error")
        mock_client_class.return_value = mock_client

        simulator.client = mock_client

        result = simulator.submit_run("test_job")

        assert result is None

    def test_select_job_from_scenario(self, simulator: LoadSimulator) -> None:
        """Test job selection from scenario."""
        scenario = {
            "job_weights": {
                "fast_job": 0.7,
                "slow_job": 0.3,
            }
        }

        # Mock random.choices to return slow_job
        with patch("random.choices", return_value=["slow_job"]):
            result = simulator._select_job_from_scenario(scenario)
            assert result == "slow_job"

    def test_select_job_default(self, simulator: LoadSimulator) -> None:
        """Test default job selection when no weights provided."""
        scenario = {}

        with patch("random.choice", return_value="fast_job"):
            result = simulator._select_job_from_scenario(scenario)
            assert result == "fast_job"


class TestLoadSimulatorCLI:
    """Test the LoadSimulator CLI."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create a CLI runner for testing."""
        return CliRunner()

    @patch("dagster_taskiq_demo.load_simulator.cli.run_steady_load")
    def test_steady_load_command(self, mock_run_steady_load: Mock, runner: CliRunner) -> None:
        """Test the steady-load CLI command."""
        mock_run_steady_load.return_value = ["run-1", "run-2", "run-3"]

        result = runner.invoke(cli, ["steady-load", "--jobs-per-minute", "6", "--duration", "60"])

        assert result.exit_code == 0
        assert "Starting steady load scenario" in result.output
        assert "Scenario completed. Submitted 3 runs." in result.output
        mock_run_steady_load.assert_called_once_with(
            jobs_per_minute=6,
            duration_seconds=60,
            host="localhost",
            port=3000,  # Default port
        )

    @patch("dagster_taskiq_demo.load_simulator.cli.run_burst_load")
    def test_burst_load_command(self, mock_run_burst_load: Mock, runner: CliRunner) -> None:
        """Test the burst-load CLI command."""
        mock_run_burst_load.return_value = ["run-1", "run-2"]

        result = runner.invoke(cli, ["burst-load", "--burst-size", "10", "--burst-interval", "5", "--duration", "120"])

        assert result.exit_code == 0
        assert "Starting burst load scenario" in result.output
        assert "Scenario completed. Submitted 2 runs." in result.output
        mock_run_burst_load.assert_called_once_with(
            burst_size=10,
            burst_interval_minutes=5,
            duration_seconds=120,
            host="localhost",
            port=3000,
        )

    @patch("dagster_taskiq_demo.load_simulator.cli.run_mixed_workload")
    def test_mixed_workload_command(self, mock_run_mixed_workload: Mock, runner: CliRunner) -> None:
        """Test the mixed-workload CLI command."""
        mock_run_mixed_workload.return_value = ["run-1", "run-2", "run-3", "run-4"]

        result = runner.invoke(cli, ["mixed-workload", "--duration", "300"])

        assert result.exit_code == 0
        assert "Starting mixed workload scenario" in result.output
        assert "Scenario completed. Submitted 4 runs." in result.output
        mock_run_mixed_workload.assert_called_once_with(
            duration_seconds=300,
            host="localhost",
            port=3000,
        )

    @patch("dagster_taskiq_demo.load_simulator.cli.run_worker_failure")
    def test_worker_failure_command(self, mock_run_worker_failure: Mock, runner: CliRunner) -> None:
        """Test the worker-failure CLI command."""
        mock_run_worker_failure.return_value = ["run-1"]

        result = runner.invoke(
            cli, ["worker-failure", "--failure-burst-size", "20", "--recovery-interval", "2", "--duration", "600"]
        )

        assert result.exit_code == 0
        assert "Starting worker failure scenario" in result.output
        assert "Scenario completed. Submitted 1 runs." in result.output
        mock_run_worker_failure.assert_called_once_with(
            failure_burst_size=20,
            recovery_interval_minutes=2,
            duration_seconds=600,
            host="localhost",
            port=3000,
        )

    @patch("dagster_taskiq_demo.load_simulator.cli.run_network_partition")
    def test_network_partition_command(self, mock_run_network_partition: Mock, runner: CliRunner) -> None:
        """Test the network-partition CLI command."""
        mock_run_network_partition.return_value = ["run-1", "run-2"]

        result = runner.invoke(cli, ["network-partition", "--max-burst-size", "5", "--duration", "300"])

        assert result.exit_code == 0
        assert "Starting network partition scenario" in result.output
        assert "Scenario completed. Submitted 2 runs." in result.output
        mock_run_network_partition.assert_called_once_with(
            max_burst_size=5,
            duration_seconds=300,
            host="localhost",
            port=3000,
        )

    def test_cli_help(self, runner: CliRunner) -> None:
        """Test CLI help output."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Load simulator CLI" in result.output
        assert "steady-load" in result.output
        assert "burst-load" in result.output
        assert "mixed-workload" in result.output
        assert "worker-failure" in result.output
        assert "network-partition" in result.output
