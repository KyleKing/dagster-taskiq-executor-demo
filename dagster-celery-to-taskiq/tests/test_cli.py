"""Simplified CLI tests for dagster-taskiq."""
from click.testing import CliRunner
from dagster_taskiq.cli import main


def test_invoke_entrypoint():
    """Test that the CLI main entry point works."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "worker" in result.output


def test_worker_help():
    """Test worker subcommand help."""
    runner = CliRunner()
    result = runner.invoke(main, ["worker", "--help"])
    assert result.exit_code == 0


def test_worker_start_help():
    """Test worker start subcommand help."""
    runner = CliRunner()
    result = runner.invoke(main, ["worker", "start", "--help"])
    assert result.exit_code == 0
    assert "Start a dagster-taskiq worker" in result.output


def test_worker_list_help():
    """Test worker list subcommand help."""
    runner = CliRunner()
    result = runner.invoke(main, ["worker", "list", "--help"])
    assert result.exit_code == 0
    assert "List information about the Taskiq queue" in result.output


# Note: Actual worker start/stop tests require LocalStack and are tested in integration tests
