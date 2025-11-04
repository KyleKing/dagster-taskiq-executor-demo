import os
import subprocess
import sys
import uuid
from collections.abc import Mapping
from typing import Any, Optional

import argparse
from dagster._config import post_process_config, validate_config
from dagster._core.errors import DagsterInvalidConfigError
from dagster._core.instance import DagsterInstance
from dagster._utils import mkdir_p
from dagster_shared.yaml_utils import load_yaml_from_path

from dagster_taskiq.executor import taskiq_executor


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {'1', 'true', 't', 'yes', 'y', 'on'}
    return bool(value)


def create_worker_parser(subparsers):
    """Create the worker subcommand parser."""
    worker_parser = subparsers.add_parser("worker", help="Worker management commands")
    worker_subparsers = worker_parser.add_subparsers(dest="worker_command", help="Worker subcommands")

    # start command
    start_parser = worker_subparsers.add_parser("start", help="Start a dagster-taskiq worker.")
    start_parser.add_argument(
        "--name", "-n",
        type=str,
        default=None,
        help='The name of the worker. Defaults to a unique name prefixed with "dagster-taskiq-".'
    )
    start_parser.add_argument(
        "--config-yaml", "-y",
        type=str,
        default=None,
        help=(
            "Specify the path to a config YAML file with options for the worker. This is the same "
            "config block that you provide to dagster_taskiq.taskiq_executor when configuring a "
            "job for execution with Taskiq, with, e.g., the URL of the SQS queue to use."
        ),
    )
    start_parser.add_argument(
        "--background", "-d",
        action="store_true",
        help="Set this flag to run the worker in the background."
    )
    start_parser.add_argument(
        "--workers", "-w",
        type=int,
        default=1,
        help="Number of worker processes to spawn.",
    )
    start_parser.add_argument(
        "--loglevel", "-l",
        type=str,
        default="INFO",
        help="Log level for the worker."
    )
    start_parser.add_argument(
        "--broker", "-b",
        type=str,
        default="dagster_taskiq.app:broker",
        help="Python path to the broker instance (default: dagster_taskiq.app:broker).",
    )
    start_parser.add_argument(
        "additional_args",
        nargs="*",
        help="Additional arguments to pass to the worker."
    )

    # dashboard command
    dashboard_parser = worker_subparsers.add_parser("dashboard", help="Start the Taskiq dashboard server.")
    dashboard_parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the dashboard server to.",
    )
    dashboard_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind the dashboard server to.",
    )
    dashboard_parser.add_argument(
        "--api-token",
        type=str,
        default="default-token",
        help="API token for dashboard authentication.",
    )
    dashboard_parser.add_argument(
        "--broker", "-b",
        type=str,
        default="dagster_taskiq.app:broker",
        help="Python path to the broker instance.",
    )

    # list command
    list_parser = worker_subparsers.add_parser("list", help="List information about the Taskiq queue.")
    list_parser.add_argument(
        "--config-yaml", "-y",
        type=str,
        default=None,
        help="Specify the path to a config YAML file with SQS queue configuration."
    )

    return worker_parser


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


def worker_start_command(args):
    """Start a Taskiq worker.

    This wraps the taskiq CLI and adds Dagster-specific configuration.
    """
    worker_name = get_worker_name(args.name)

    # Build taskiq worker command
    # Use sys.executable to ensure we use the same Python interpreter
    subprocess_args = [
        sys.executable,
        "-m",
        "taskiq",
        "worker",
        args.broker,
        "--log-level", args.loglevel.upper(),
        "--workers", str(args.workers),
        "dagster_taskiq.tasks",  # Module containing tasks
    ]

    # Note: Taskiq doesn't support worker names like Celery

    # Set up environment with config
    env = os.environ.copy()
    validated_config: Mapping[str, Any] = (
        get_validated_config(args.config_yaml) if args.config_yaml else {}
    )

    config_source = validated_config.get("config_source") if isinstance(validated_config, Mapping) else None
    enable_cancellation = True
    if isinstance(config_source, Mapping) and "enable_cancellation" in config_source:
        enable_cancellation = _coerce_bool(config_source["enable_cancellation"])

    env_override = env.get("DAGSTER_TASKIQ_ENABLE_CANCELLATION")
    if env_override is not None:
        enable_cancellation = _coerce_bool(env_override)
    env["DAGSTER_TASKIQ_ENABLE_CANCELLATION"] = "1" if enable_cancellation else "0"

    # If config YAML provided, extract and set environment variables
    if args.config_yaml:
        if validated_config.get("queue_url"):
            env["DAGSTER_TASKIQ_SQS_QUEUE_URL"] = str(validated_config["queue_url"])

        if validated_config.get("region_name"):
            env["AWS_DEFAULT_REGION"] = str(validated_config["region_name"])

        if validated_config.get("endpoint_url"):
            env["DAGSTER_TASKIQ_SQS_ENDPOINT_URL"] = str(validated_config["endpoint_url"])

        # Add config module to PYTHONPATH if needed
        config_dir = get_config_module(args.config_yaml)
        if config_dir:
            existing_pythonpath = env.get("PYTHONPATH", "")
            if existing_pythonpath and not existing_pythonpath.endswith(os.pathsep):
                existing_pythonpath += os.pathsep
            env["PYTHONPATH"] = f"{existing_pythonpath}{config_dir}{os.pathsep}"

    has_receiver_override = any(
        arg == "--receiver" or arg.startswith("--receiver=") for arg in args.additional_args
    )
    if enable_cancellation and not has_receiver_override:
        subprocess_args.extend(
            ["--receiver", "dagster_taskiq.cancellable_receiver:CancellableReceiver"]
        )

    # Add any additional args
    subprocess_args.extend(args.additional_args)

    print(f"Starting Taskiq worker: {worker_name}")
    print(f"Broker: {args.broker}")
    print(f"Workers: {args.workers}")
    print(f"Log level: {args.loglevel}")

    if args.background:
        print("Running in background mode...")
        launch_background_worker(subprocess_args, env=env)
        print("Worker started in background.")
    else:
        return subprocess.check_call(subprocess_args, env=env)


def dashboard_command(args):
    """Start the Taskiq dashboard server."""
    try:
        from taskiq_dashboard import TaskiqDashboard
    except ImportError:
        print("Error: taskiq-dashboard is not installed.")
        print("Install it with: uv pip install taskiq-dashboard")
        print("Or install dev dependencies: uv sync --group dev")
        return

    print(f"Starting Taskiq dashboard on {args.host}:{args.port}")
    print(f"Broker: {args.broker}")

    # Import the broker
    module_name, attr_name = args.broker.split(":")
    module = __import__(module_name, fromlist=[attr_name])
    broker_instance = getattr(module, attr_name)

    # Create and run the dashboard
    dashboard = TaskiqDashboard(
        api_token=args.api_token,
        broker=broker_instance,
        uvicorn_kwargs={"host": args.host, "port": args.port}
    )
    dashboard.run()


def worker_list_command(args):
    """List SQS queue attributes.

    Note: Unlike Celery, Taskiq doesn't have a built-in worker registry.
    This command shows SQS queue statistics instead.
    """
    try:
        import boto3
    except ImportError:
        print("Error: boto3 is required for this command. Install it with: pip install boto3")
        return

    validated_config = get_validated_config(args.config_yaml) if args.config_yaml else {}

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
        print("Error: No queue URL configured. Set DAGSTER_TASKIQ_SQS_QUEUE_URL or provide --config-yaml")
        return

    print(f"Queue URL: {queue_url}")
    print(f"Region: {region_name}")

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
        print("\nQueue Statistics:")
        print(f"  Messages available: {attrs.get('ApproximateNumberOfMessages', 'N/A')}")
        print(f"  Messages in flight: {attrs.get('ApproximateNumberOfMessagesNotVisible', 'N/A')}")
        print(f"  Messages delayed: {attrs.get('ApproximateNumberOfMessagesDelayed', 'N/A')}")

    except Exception as e:
        print(f"Error querying SQS: {e}")


def main():
    """dagster-taskiq CLI."""
    parser = argparse.ArgumentParser(description="dagster-taskiq CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create worker subcommand
    create_worker_parser(subparsers)

    args = parser.parse_args()

    if args.command == "worker":
        if args.worker_command == "start":
            worker_start_command(args)
        elif args.worker_command == "dashboard":
            dashboard_command(args)
        elif args.worker_command == "list":
            worker_list_command(args)
        else:
            parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
