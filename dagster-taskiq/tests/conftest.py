import os
import socket
import tempfile
import time
from collections.abc import Iterator

import boto3
import pytest
from dagster._core.instance import DagsterInstance
from dagster._core.test_utils import environ, instance_for_test
from moto.server import ThreadedMotoServer
# from dagster_test.test_project import build_and_tag_test_image, get_test_project_docker_image

from tests.utils import start_taskiq_worker

AWS_TEST_ACCESS_KEY = "testing"
AWS_TEST_SECRET_KEY = "testing"
AWS_TEST_REGION = "us-east-1"


def find_free_port() -> int:
    """Find an available port for the moto server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture(scope="session")
def localstack():
    """Provide moto-backed AWS endpoints for tests expecting LocalStack."""
    endpoint_override = os.getenv("DAGSTER_TASKIQ_SQS_ENDPOINT_URL")
    queue_override = os.getenv("DAGSTER_TASKIQ_SQS_QUEUE_URL")

    if endpoint_override and queue_override:
        env_vars = {
            "DAGSTER_TASKIQ_SQS_QUEUE_URL": queue_override,
            "DAGSTER_TASKIQ_SQS_ENDPOINT_URL": endpoint_override,
            "DAGSTER_TASKIQ_S3_ENDPOINT_URL": os.getenv(
                "DAGSTER_TASKIQ_S3_ENDPOINT_URL", endpoint_override
            ),
            "DAGSTER_TASKIQ_S3_BUCKET_NAME": os.getenv(
                "DAGSTER_TASKIQ_S3_BUCKET_NAME", "dagster-taskiq-results"
            ),
            "AWS_DEFAULT_REGION": os.getenv("AWS_DEFAULT_REGION", AWS_TEST_REGION),
            "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", AWS_TEST_ACCESS_KEY),
            "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", AWS_TEST_SECRET_KEY),
        }
        with environ(env_vars):
            yield queue_override
        return

    # Temporarily remove any global endpoint configuration for moto
    removed_vars = {}
    for var_name in ["AWS_ENDPOINT_URL", "AWS_SQS_ENDPOINT_URL", "AWS_S3_ENDPOINT_URL"]:
        if var_name in os.environ:
            removed_vars[var_name] = os.environ.pop(var_name)

    # Find an available port (avoiding 5000 which conflicts with macOS AirPlay)
    port = find_free_port()
    server = ThreadedMotoServer(port=port, verbose=False)
    server.start()

    endpoint_url = f"http://127.0.0.1:{port}"

    try:
        sqs = boto3.client(
            "sqs",
            endpoint_url=endpoint_url,
            region_name=AWS_TEST_REGION,
            aws_access_key_id=AWS_TEST_ACCESS_KEY,
            aws_secret_access_key=AWS_TEST_SECRET_KEY,
        )
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=AWS_TEST_REGION,
            aws_access_key_id=AWS_TEST_ACCESS_KEY,
            aws_secret_access_key=AWS_TEST_SECRET_KEY,
        )

        unique_suffix = int(time.time())
        queue_name = f"dagster-tasks-test-{unique_suffix}"
        queue_url = sqs.create_queue(QueueName=queue_name)["QueueUrl"]
        cancel_queue_name = f"{queue_name}-cancels"
        sqs.create_queue(QueueName=cancel_queue_name)

        bucket_name = f"dagster-taskiq-test-{unique_suffix}"
        s3.create_bucket(Bucket=bucket_name)

        env_vars = {
            "DAGSTER_TASKIQ_SQS_QUEUE_URL": queue_url,
            "DAGSTER_TASKIQ_S3_BUCKET_NAME": bucket_name,
            "AWS_DEFAULT_REGION": AWS_TEST_REGION,
            "AWS_ACCESS_KEY_ID": AWS_TEST_ACCESS_KEY,
            "AWS_SECRET_ACCESS_KEY": AWS_TEST_SECRET_KEY,
            "DAGSTER_TASKIQ_SQS_ENDPOINT_URL": endpoint_url,
            "DAGSTER_TASKIQ_S3_ENDPOINT_URL": endpoint_url,
        }

        with environ(env_vars):
            import importlib

            import dagster_taskiq  # type: ignore
            import dagster_taskiq.defaults as taskiq_defaults  # type: ignore
            importlib.reload(taskiq_defaults)  # reload defaults first

            import dagster_taskiq.app as taskiq_app  # type: ignore
            import dagster_taskiq.executor as taskiq_executor_module  # type: ignore
            import dagster_taskiq.launcher as taskiq_launcher  # type: ignore
            import dagster_taskiq.make_app as taskiq_make_app  # type: ignore
            import dagster_taskiq.tasks as taskiq_tasks  # type: ignore

            for module in (
                taskiq_executor_module,
                taskiq_launcher,
                taskiq_make_app,
                taskiq_app,
                taskiq_tasks,
            ):
                importlib.reload(module)

            importlib.reload(dagster_taskiq)

            try:
                import tests.repo as taskiq_test_repo  # type: ignore
            except ModuleNotFoundError:
                taskiq_test_repo = None  # type: ignore[assignment]
            else:
                importlib.reload(taskiq_test_repo)  # type: ignore[arg-type]

            try:
                yield queue_url
            finally:
                pass
    finally:
        # Stop the server after all tests complete
        server.stop()
        # Restore the environment variables
        os.environ.update(removed_vars)


@pytest.fixture(scope="function")
def tempdir():
    with tempfile.TemporaryDirectory() as the_dir:
        yield the_dir


@pytest.fixture(scope="function")
def instance(tempdir):
    with instance_for_test(temp_dir=tempdir) as test_instance:
        yield test_instance


@pytest.fixture(scope="function")
def dagster_taskiq_worker(localstack, instance: DagsterInstance) -> Iterator[None]:
    with start_taskiq_worker():
        yield


# @pytest.fixture(scope="session")
# def dagster_docker_image():
#     docker_image = get_test_project_docker_image()
#
#     if not IS_BUILDKITE:
#         try:
#             client = docker.from_env()
#             client.images.get(docker_image)
#             print(  # noqa: T201
#                 f"Found existing image tagged {docker_image}, skipping image build. To rebuild, first run: "
#                 f"docker rmi {docker_image}"
#             )
#         except docker.errors.ImageNotFound:  # pyright: ignore[reportAttributeAccessIssue]
#             build_and_tag_test_image(docker_image)
#
#     return docker_image
