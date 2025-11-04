"""Simplified configuration tests for dagster-taskiq.

Note: Unlike Celery, Taskiq doesn't require dynamic config file generation.
Configuration is handled via environment variables and YAML files directly.
"""

from dagster._core.test_utils import environ, instance_for_test


def test_basic_environment_config():
    """Test that basic environment configuration works."""
    with (
        instance_for_test(),
        environ({
            "DAGSTER_TASKIQ_SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123/test",
            "AWS_DEFAULT_REGION": "us-east-1",
        }),
    ):
        # Reload module to pick up environment variables
        import importlib  # noqa: PLC0415

        import dagster_taskiq.defaults  # noqa: PLC0415

        importlib.reload(dagster_taskiq.defaults)
        from dagster_taskiq.defaults import aws_region_name, sqs_queue_url  # noqa: PLC0415

        assert sqs_queue_url == "https://sqs.us-east-1.amazonaws.com/123/test"
        assert aws_region_name == "us-east-1"


def test_endpoint_url_config():
    """Test custom endpoint URL configuration used in tests (moto)."""
    with (
        instance_for_test(),
        environ({
            "DAGSTER_TASKIQ_SQS_ENDPOINT_URL": "http://localhost:4566",
        }),
    ):
        # Reload module to pick up new environment variables
        import importlib  # noqa: PLC0415

        import dagster_taskiq.defaults  # noqa: PLC0415

        importlib.reload(dagster_taskiq.defaults)
        from dagster_taskiq.defaults import sqs_endpoint_url  # noqa: PLC0415

        assert sqs_endpoint_url == "http://localhost:4566"


# Note: Taskiq uses simpler configuration than Celery - no dynamic config file generation needed
