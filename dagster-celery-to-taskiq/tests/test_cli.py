"""Simplified CLI tests for dagster-taskiq."""
from unittest.mock import patch
from dagster_taskiq.cli import main


def test_invoke_entrypoint():
    """Test that the CLI main entry point works."""
    with patch('sys.argv', ['dagster-taskiq', '--help']):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0


def test_worker_help():
    """Test worker subcommand help."""
    with patch('sys.argv', ['dagster-taskiq', 'worker', '--help']):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0


def test_worker_start_help():
    """Test worker start subcommand help."""
    with patch('sys.argv', ['dagster-taskiq', 'worker', 'start', '--help']):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0


def test_worker_list_help():
    """Test worker list subcommand help."""
    with patch('sys.argv', ['dagster-taskiq', 'worker', 'list', '--help']):
        try:
            main()
        except SystemExit as e:
            assert e.code == 0


# Note: Actual worker start/stop tests require LocalStack and are tested in integration tests
