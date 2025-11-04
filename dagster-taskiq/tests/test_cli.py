"""Simplified CLI tests for dagster-taskiq."""

from unittest.mock import patch

import pytest

from dagster_taskiq.cli import main


def test_invoke_entrypoint():
    """Test that the CLI main entry point works."""
    with patch("sys.argv", ["dagster-taskiq", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


def test_worker_help():
    """Test worker subcommand help."""
    with patch("sys.argv", ["dagster-taskiq", "worker", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


def test_worker_start_help():
    """Test worker start subcommand help."""
    with patch("sys.argv", ["dagster-taskiq", "worker", "start", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


def test_worker_list_help():
    """Test worker list subcommand help."""
    with patch("sys.argv", ["dagster-taskiq", "worker", "list", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


# Note: Actual worker start/stop tests require LocalStack and are tested in integration tests
