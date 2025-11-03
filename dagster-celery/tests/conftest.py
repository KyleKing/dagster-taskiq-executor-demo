import os
import subprocess
import tempfile
import time
from collections.abc import Iterator

import docker
import pytest
from dagster import file_relative_path
from dagster._core.instance import DagsterInstance
from dagster._core.test_utils import environ, instance_for_test
# from dagster_test.test_project import build_and_tag_test_image, get_test_project_docker_image

from tests.utils import start_taskiq_worker

IS_BUILDKITE = os.getenv("BUILDKITE") is not None


@pytest.fixture(scope="session")
def localstack():
    """Start LocalStack for SQS testing."""
    if IS_BUILDKITE:
        # On Buildkite, assume LocalStack is already running
        queue_url = os.getenv(
            "DAGSTER_TASKIQ_SQS_QUEUE_URL",
            "https://sqs.us-east-1.amazonaws.com/000000000000/dagster-test-queue"
        )
        with environ({
            "DAGSTER_TASKIQ_SQS_QUEUE_URL": queue_url,
            "DAGSTER_TASKIQ_SQS_ENDPOINT_URL": os.getenv("DAGSTER_TASKIQ_SQS_ENDPOINT_URL", "http://localhost:4566"),
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
        }):
            yield queue_url
        return

    # Start LocalStack container
    try:
        # Stop and remove existing container
        subprocess.run(["docker", "stop", "dagster-localstack"], capture_output=True)
        subprocess.run(["docker", "rm", "dagster-localstack"], capture_output=True)
    except Exception:
        pass

    # Start fresh LocalStack container
    subprocess.check_output([
        "docker", "run", "-d",
        "--name", "dagster-localstack",
        "-p", "4566:4566",
        "-e", "SERVICES=sqs",
        "localstack/localstack:latest"
    ])

    print("Waiting for LocalStack to be ready...")  # noqa: T201
    max_retries = 30
    for i in range(max_retries):
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:4566/_localstack/health"],
                capture_output=True,
                timeout=5
            )
            if b'"sqs":' in result.stdout and b'"available"' in result.stdout:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("LocalStack failed to start")

    # Create SQS queue
    queue_name = "dagster-test-queue"
    result = subprocess.check_output([
        "aws", "--endpoint-url=http://localhost:4566",
        "sqs", "create-queue",
        "--queue-name", queue_name,
        "--region", "us-east-1"
    ])

    # Extract queue URL from response
    import json
    queue_data = json.loads(result)
    queue_url = queue_data["QueueUrl"]

    # Set environment variables
    with environ({
        "DAGSTER_TASKIQ_SQS_QUEUE_URL": queue_url,
        "DAGSTER_TASKIQ_SQS_ENDPOINT_URL": "http://localhost:4566",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
    }):
        try:
            yield queue_url
        finally:
            # Clean up
            try:
                subprocess.check_output(["docker", "stop", "dagster-localstack"])
                subprocess.check_output(["docker", "rm", "dagster-localstack"])
            except Exception:
                pass


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
