import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator

import boto3
from botocore.exceptions import ClientError
import pytest
from dagster._core.instance import DagsterInstance
from dagster._core.test_utils import environ, instance_for_test
# from dagster_test.test_project import build_and_tag_test_image, get_test_project_docker_image

from tests.utils import start_taskiq_worker

IS_BUILDKITE = os.getenv("BUILDKITE") is not None


def _service_ready(entry: object) -> bool:
    if isinstance(entry, str):
        return entry.lower() in {"running", "available", "ready"}
    if isinstance(entry, dict):  # type: ignore[reportGeneralTypeIssues]
        status = entry.get("status") or entry.get("state")
        if isinstance(status, str):
            return status.lower() in {"running", "available", "ready"}
    return False


def _wait_for_localstack(endpoint: str, timeout: int = 30) -> None:
    for _ in range(timeout):
        try:
            with urllib.request.urlopen(f"{endpoint}/_localstack/health", timeout=2) as response:
                payload = response.read()
                data = json.loads(payload.decode("utf-8"))
                services = data.get("services") or {}
                if _service_ready(services.get("sqs")) and _service_ready(services.get("s3")):
                    return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("LocalStack failed to report healthy status within timeout")


def _allocate_localstack_port(preferred: int = 4566) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _rewrite_queue_url_port(queue_url: str, port: int) -> str:
    parsed = urllib.parse.urlparse(queue_url)
    host = parsed.hostname or "localhost"
    netloc = f"{host}:{port}"
    if parsed.username or parsed.password:
        auth = f"{parsed.username}:{parsed.password}@"
        netloc = f"{auth}{netloc}"
    return urllib.parse.urlunparse(parsed._replace(netloc=netloc))


@pytest.fixture(scope="session")
def localstack():
    """Start LocalStack for SQS testing."""
    if IS_BUILDKITE:
        endpoint = os.getenv("DAGSTER_TASKIQ_SQS_ENDPOINT_URL", "http://localhost:4566")
        queue_url = os.getenv(
            "DAGSTER_TASKIQ_SQS_QUEUE_URL",
            "https://sqs.us-east-1.amazonaws.com/000000000000/dagster-test-queue",
        )
        env_vars = {
            "DAGSTER_TASKIQ_SQS_QUEUE_URL": queue_url,
            "DAGSTER_TASKIQ_SQS_ENDPOINT_URL": endpoint,
            "DAGSTER_TASKIQ_S3_ENDPOINT_URL": os.getenv(
                "DAGSTER_TASKIQ_S3_ENDPOINT_URL", endpoint
            ),
            "DAGSTER_TASKIQ_S3_BUCKET_NAME": os.getenv(
                "DAGSTER_TASKIQ_S3_BUCKET_NAME", "dagster-taskiq-results"
            ),
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
        }
        with environ(env_vars):
            yield queue_url
        return

    host_port = _allocate_localstack_port()
    container_name = f"dagster-localstack-{host_port}"
    endpoint = f"http://127.0.0.1:{host_port}"

    try:
        subprocess.run(["docker", "stop", container_name], capture_output=True, check=False)
        subprocess.run(["docker", "rm", container_name], capture_output=True, check=False)
    except FileNotFoundError:
        pytest.skip("Docker CLI is required to run LocalStack-backed tests")

    try:
        subprocess.check_output(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-p",
                f"{host_port}:4566",
                "-e",
                "SERVICES=sqs,s3",
                "localstack/localstack:latest",
            ],
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"Unable to start LocalStack container: {exc.output.decode().strip()}")
    except FileNotFoundError:
        pytest.skip("Docker CLI is required to run LocalStack-backed tests")

    try:
        _wait_for_localstack(endpoint)
    except RuntimeError as exc:
        subprocess.run(["docker", "stop", container_name], capture_output=True, check=False)
        subprocess.run(["docker", "rm", container_name], capture_output=True, check=False)
        pytest.skip(str(exc))

    sqs = boto3.client(
        "sqs",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    queue_name = "dagster-tasks"
    queue_url = _rewrite_queue_url_port(
        sqs.create_queue(QueueName=queue_name)["QueueUrl"], host_port
    )

    for _ in range(10):
        try:
            sqs.get_queue_url(QueueName=queue_name)
            break
        except ClientError:
            time.sleep(1)
    else:
        raise RuntimeError("LocalStack SQS queue was not ready in time")

    cancel_queue_name = f"{queue_name}-cancels"
    sqs.create_queue(QueueName=cancel_queue_name)

    bucket_name = "dagster-taskiq-results"
    try:
        s3.create_bucket(Bucket=bucket_name)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise

    env_vars = {
        "DAGSTER_TASKIQ_SQS_QUEUE_URL": queue_url,
        "DAGSTER_TASKIQ_SQS_ENDPOINT_URL": endpoint,
        "DAGSTER_TASKIQ_S3_ENDPOINT_URL": endpoint,
        "DAGSTER_TASKIQ_S3_BUCKET_NAME": bucket_name,
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
    }

    with environ(env_vars):
        try:
            yield queue_url
        finally:
            try:
                subprocess.run(["docker", "stop", container_name], capture_output=True, check=False)
                subprocess.run(["docker", "rm", container_name], capture_output=True, check=False)
            except FileNotFoundError:
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
