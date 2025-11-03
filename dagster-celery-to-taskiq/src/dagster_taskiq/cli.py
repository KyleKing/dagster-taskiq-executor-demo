import os
import subprocess
import uuid
from collections.abc import Mapping
from typing import Any, Optional

import click
import dagster._check as check
from dagster._config import post_process_config, validate_config
from dagster._core.errors import DagsterInvalidConfigError
from dagster._core.instance import DagsterInstance
from dagster._utils import mkdir_p
from dagster_shared.yaml_utils import load_yaml_from_path

from dagster_taskiq.executor import TaskiqExecutor, taskiq_executor


def create_worker_cli_group():
    """Create the worker CLI command group."""
    group = click.Group(name="worker")
    group.add_command(worker_start_command)
    group.add_command(worker_list_command)
    group.add_command(dashboard_command)
    return group


def get_config_value_from_yaml(yaml_path: Optional[str]) -> Mapping[str, Any]:
    """Extract executor config from YAML file.

    Args:
        yaml_path: Path to YAML configuration file

    Returns:
        Configuration dictionary
    """
    if yaml_path is None:
        return {}
    parsed_yaml = load_yaml_from_path(yaml_path) or {}
    assert isinstance(parsed_yaml, dict)
    # Extract config from execution block
    return parsed_yaml.get("execution", {}).get("config", {}) or {}


def get_worker_name(name: Optional[str] = None) -> str:
    """Generate a worker name.

    Args:
        name: Optional custom worker name

    Returns:
        Worker name string
    """
    if name is not None:
        return name
    return f"dagster-taskiq-{str(uuid.uuid4())[-6:]}"


def get_validated_config(config_yaml: Optional[str] = None) -> Any:
    """Validate configuration from YAML file.

    Args:
        config_yaml: Path to YAML configuration file

    Returns:
        Validated configuration dictionary

    Raises:
        DagsterInvalidConfigError: If configuration is invalid
    """
    config_type = taskiq_executor.config_schema.config_type
    config_value = get_config_value_from_yaml(config_yaml)
    config = validate_config(config_type, config_value)
    if not config.success:
        raise DagsterInvalidConfigError(
            f"Errors while loading Taskiq executor config at {config_yaml}.",
            config.errors,
            config_value,
        )
    return post_process_config(config_type, config_value).value  # type: ignore


def get_config_module(config_yaml=None):
    """Create a configuration module for the worker.

    Args:
        config_yaml: Path to YAML configuration file

    Returns:
        Path to configuration directory
    """
    instance = DagsterInstance.get()

    config_module_name = "dagster_taskiq_config"

    config_dir = os.path.join(
        instance.root_directory, "dagster_taskiq", "config", str(uuid.uuid4())
    )
    mkdir_p(config_dir)
    config_path = os.path.join(config_dir, f"{config_module_name}.py")

    validated_config = get_validated_config(config_yaml)
    with open(config_path, "w", encoding="utf8") as fd:
        if validated_config.get("queue_url"):
            fd.write(
                f"QUEUE_URL = {validated_config['queue_url']!r}\n"
            )
        if validated_config.get("region_name"):
            fd.write(
                f"REGION_NAME = {validated_config['region_name']!r}\n"
            )
        if validated_config.get("endpoint_url"):
            fd.write(
                f"ENDPOINT_URL = {validated_config['endpoint_url']!r}\n"
            )
        if validated_config.get("config_source"):
            for key, value in validated_config["config_source"].items():
                fd.write(f"{key} = {value!r}\n")

    return config_dir


def launch_background_worker(subprocess_args, env):
    """Launch a worker in background mode.

    Args:
        subprocess_args: Command line arguments
        env: Environment variables

    Returns:
        Subprocess handle
    """
    return subprocess.Popen(
        subprocess_args, stdout=None, stderr=None, env=env
    )


@click.command(name="start", help="Start a dagster-taskiq worker.")
@click.option(
    "--name",
    "-n",
    type=click.STRING,
    default=None,
    help=(
        'The name of the worker. Defaults to a unique name prefixed with "dagster-taskiq-".'
    ),
)
@click.option(
    "--config-yaml",
    "-y",
    type=click.Path(exists=True),
    default=None,
    help=(
        "Specify the path to a config YAML file with options for the worker. This is the same "
        "config block that you provide to dagster_taskiq.taskiq_executor when configuring a "
        "job for execution with Taskiq, with, e.g., the URL of the SQS queue to use."
    ),
)
@click.option(
    "--background", "-d", is_flag=True, help="Set this flag to run the worker in the background."
)
@click.option(
    "--workers",
    "-w",
    type=click.INT,
    default=1,
    help="Number of worker processes to spawn.",
)
@click.option(
    "--loglevel", "-l", type=click.STRING, default="INFO", help="Log level for the worker."
)
@click.option(
    "--broker",
    "-b",
    type=click.STRING,
    default="dagster_taskiq.app:broker",
    help="Python path to the broker instance (default: dagster_taskiq.app:broker).",
)
@click.argument("additional_args", nargs=-1, type=click.UNPROCESSED)
def worker_start_command(
    name,
    config_yaml,
    background,
    workers,
    loglevel,
    broker,
    additional_args,
):
    """Start a Taskiq worker.

    This wraps the taskiq CLI and adds Dagster-specific configuration.
    """
    worker_name = get_worker_name(name)

    # Build taskiq worker command
    subprocess_args = [
        "taskiq",
        "worker",
        broker,
        "--log-level", loglevel.upper(),
        "--workers", str(workers),
        "dagster_taskiq.tasks",  # Module containing tasks
    ]

    # Note: Taskiq doesn't support worker names like Celery

    # Add any additional args
    subprocess_args.extend(additional_args)

    # Set up environment with config
    env = os.environ.copy()

    # If config YAML provided, extract and set environment variables
    if config_yaml:
        validated_config = get_validated_config(config_yaml)

        if validated_config.get("queue_url"):
            env["DAGSTER_TASKIQ_SQS_QUEUE_URL"] = str(validated_config["queue_url"])

        if validated_config.get("region_name"):
            env["AWS_DEFAULT_REGION"] = str(validated_config["region_name"])

        if validated_config.get("endpoint_url"):
            env["DAGSTER_TASKIQ_SQS_ENDPOINT_URL"] = str(validated_config["endpoint_url"])

        # Add config module to PYTHONPATH if needed
        config_dir = get_config_module(config_yaml)
        if config_dir:
            existing_pythonpath = env.get("PYTHONPATH", "")
            if existing_pythonpath and not existing_pythonpath.endswith(os.pathsep):
                existing_pythonpath += os.pathsep
            env["PYTHONPATH"] = f"{existing_pythonpath}{config_dir}{os.pathsep}"

    click.echo(f"Starting Taskiq worker: {worker_name}")
    click.echo(f"Broker: {broker}")
    click.echo(f"Workers: {workers}")
    click.echo(f"Log level: {loglevel}")

    if background:
        click.echo("Running in background mode...")
        launch_background_worker(subprocess_args, env=env)
        click.echo("Worker started in background.")
    else:
        return subprocess.check_call(subprocess_args, env=env)


@click.command(
    name="dashboard",
    help="Start the Taskiq dashboard server.",
)
@click.option(
    "--host",
    type=click.STRING,
    default="0.0.0.0",
    help="Host to bind the dashboard server to.",
)
@click.option(
    "--port",
    type=click.INT,
    default=8080,
    help="Port to bind the dashboard server to.",
)
@click.option(
    "--api-token",
    type=click.STRING,
    default="default-token",
    help="API token for dashboard authentication.",
)
@click.option(
    "--broker",
    "-b",
    type=click.STRING,
    default="dagster_taskiq.app:broker",
    help="Python path to the broker instance.",
)
def dashboard_command(host, port, api_token, broker):
    """Start the Taskiq dashboard server."""
    try:
        from taskiq_dashboard import TaskiqDashboard
    except ImportError:
        click.echo("Error: taskiq-dashboard is not installed. Install it with: pip install taskiq-dashboard")
        return

    click.echo(f"Starting Taskiq dashboard on {host}:{port}")
    click.echo(f"Broker: {broker}")

    # Import the broker
    module_name, attr_name = broker.split(":")
    module = __import__(module_name, fromlist=[attr_name])
    broker_instance = getattr(module, attr_name)

    # Create and run the dashboard
    dashboard = TaskiqDashboard(
        api_token=api_token,
        broker=broker_instance,
        uvicorn_kwargs={"host": host, "port": port}
    )
    dashboard.run()


@click.command(
    name="list",
    help="List information about the Taskiq queue.",
)
@click.option(
    "--config-yaml",
    "-y",
    type=click.Path(exists=True),
    default=None,
    help=(
        "Specify the path to a config YAML file with SQS queue configuration."
    ),
)
def worker_list_command(config_yaml=None):
    """List SQS queue attributes.

    Note: Unlike Celery, Taskiq doesn't have a built-in worker registry.
    This command shows SQS queue statistics instead.
    """
    try:
        import boto3
    except ImportError:
        click.echo("Error: boto3 is required for this command. Install it with: pip install boto3")
        return

    validated_config = get_validated_config(config_yaml) if config_yaml else {}

    queue_url = validated_config.get(
        "queue_url",
        os.getenv("DAGSTER_TASKIQ_SQS_QUEUE_URL")
    )
    endpoint_url = validated_config.get(
        "endpoint_url",
        os.getenv("DAGSTER_TASKIQ_SQS_ENDPOINT_URL")
    )
    region_name = validated_config.get(
        "region_name",
        os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )

    if not queue_url:
        click.echo("Error: No queue URL configured. Set DAGSTER_TASKIQ_SQS_QUEUE_URL or provide --config-yaml")
        return

    click.echo(f"Queue URL: {queue_url}")
    click.echo(f"Region: {region_name}")

    try:
        sqs = boto3.client(
            "sqs",
            endpoint_url=endpoint_url,
            region_name=region_name,
        )

        # Get queue attributes
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
            ]
        )

        attrs = response.get("Attributes", {})
        click.echo("\nQueue Statistics:")
        click.echo(f"  Messages available: {attrs.get('ApproximateNumberOfMessages', 'N/A')}")
        click.echo(f"  Messages in flight: {attrs.get('ApproximateNumberOfMessagesNotVisible', 'N/A')}")
        click.echo(f"  Messages delayed: {attrs.get('ApproximateNumberOfMessagesDelayed', 'N/A')}")

    except Exception as e:
        click.echo(f"Error querying SQS: {e}")


worker_cli = create_worker_cli_group()


@click.group(commands={"worker": worker_cli})
def main():
    """dagster-taskiq CLI."""


if __name__ == "__main__":
    main()
