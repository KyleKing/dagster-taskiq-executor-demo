"""Pytest plugin for automatic LocalStack + Pulumi state synchronization.

Add this to your conftest.py to automatically handle state divergence:

    # conftest.py
    pytest_plugins = ["pytest_localstack_sync"]

Or import the fixtures directly:

    # conftest.py
    from pytest_localstack_sync import *
"""

import subprocess
import time
from typing import Generator

import pytest
import requests


def is_localstack_running(endpoint: str = "http://localhost:4566") -> bool:
    """Check if LocalStack is running."""
    try:
        response = requests.get(f"{endpoint}/_localstack/health", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def wait_for_localstack(
    endpoint: str = "http://localhost:4566",
    timeout: int = 30
) -> bool:
    """Wait for LocalStack to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_localstack_running(endpoint):
            return True
        time.sleep(1)
    return False


def start_localstack_container() -> None:
    """Start LocalStack container if not running."""
    if is_localstack_running():
        print("LocalStack already running")
        return

    print("Starting LocalStack container...")

    # Check if container exists but is stopped
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=localstack", "--format", "{{.Names}}"],
        capture_output=True,
        text=True,
        check=False
    )

    if "localstack" in result.stdout:
        # Container exists, just start it
        subprocess.run(["docker", "start", "localstack"], check=True)
    else:
        # Create new container
        subprocess.run([
            "docker", "run", "-d",
            "--name", "localstack",
            "-p", "4566:4566",
            "-e", "SERVICES=s3,sqs,dynamodb,iam,sts,lambda,ecs,rds,ec2",
            "-e", "DEBUG=1",
            "-e", "PERSISTENCE=1",
            "-e", "DATA_DIR=/tmp/localstack/data",
            "-v", "localstack-data:/tmp/localstack",
            "localstack/localstack:latest"
        ], check=True)

    if not wait_for_localstack():
        raise RuntimeError("LocalStack failed to start")

    print("LocalStack is ready")


def sync_pulumi_state() -> None:
    """Sync Pulumi state with LocalStack reality."""
    print("Syncing Pulumi state with LocalStack...")

    result = subprocess.run(
        ["pulumi", "refresh", "--yes"],
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        print("Warning: Pulumi refresh failed")
        print(result.stderr)
        print("State may be diverged - consider destroying and redeploying")


@pytest.fixture(scope="session", autouse=True)
def ensure_localstack() -> Generator[None, None, None]:
    """Automatically ensure LocalStack is running before tests.

    This fixture:
    - Starts LocalStack if not running
    - Syncs Pulumi state with LocalStack reality
    - Runs before all tests (session scope)
    - Is automatic (autouse=True)
    """
    # Setup: ensure LocalStack is running
    start_localstack_container()

    # Sync state before running tests
    sync_pulumi_state()

    yield

    # Teardown: optionally stop LocalStack
    # (commented out to keep it running for faster subsequent test runs)
    # subprocess.run(["docker", "stop", "localstack"], check=False)


@pytest.fixture(scope="function")
def localstack_state_sync() -> Generator[None, None, None]:
    """Sync Pulumi state before and after each test.

    Use this for tests that may modify infrastructure:

        def test_my_infrastructure(localstack_state_sync):
            # State is synced before test
            ...
            # State is synced after test
    """
    # Pre-test: sync state
    sync_pulumi_state()

    yield

    # Post-test: sync state to catch any drift
    sync_pulumi_state()


@pytest.fixture(scope="function")
def fresh_localstack() -> Generator[None, None, None]:
    """Provide a fresh LocalStack for test isolation.

    This is expensive but provides complete isolation:

        def test_isolated_infrastructure(fresh_localstack):
            # Fresh LocalStack, no existing resources
            ...
    """
    # Reset LocalStack by restarting it
    print("Restarting LocalStack for fresh state...")

    subprocess.run(["docker", "restart", "localstack"], check=True)

    if not wait_for_localstack():
        raise RuntimeError("LocalStack failed to restart")

    # Clear Pulumi state
    subprocess.run([
        "pulumi", "stack", "export"
    ], capture_output=True, check=True)

    # Import empty state
    empty_state = {
        "version": 3,
        "deployment": {
            "manifest": {"time": "", "magic": "", "version": ""},
            "secrets_providers": {"type": "passphrase"},
            "resources": []
        }
    }

    import json
    proc = subprocess.Popen(
        ["pulumi", "stack", "import"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    proc.communicate(input=json.dumps(empty_state))

    yield

    # Cleanup: destroy resources
    subprocess.run(["pulumi", "destroy", "--yes"], check=False)


@pytest.fixture
def localstack_endpoint() -> str:
    """Get LocalStack endpoint URL.

    Use for configuring AWS clients:

        def test_s3(localstack_endpoint):
            import boto3
            s3 = boto3.client("s3", endpoint_url=localstack_endpoint)
    """
    return "http://localhost:4566"


# Pytest hook to handle state divergence errors
def pytest_exception_interact(node, call, report):
    """Handle exceptions related to state divergence."""
    if call.excinfo and "ResourceNotFound" in str(call.excinfo.value):
        print("\n" + "=" * 70)
        print("DETECTED: Pulumi/LocalStack state divergence")
        print("=" * 70)
        print("\nPossible causes:")
        print("  - LocalStack container was restarted")
        print("  - Resources were deleted outside of Pulumi")
        print("  - State file is corrupted")
        print("\nSolutions:")
        print("  1. Run: pulumi refresh --yes")
        print("  2. Run: ./scripts/localstack-dev.sh sync")
        print("  3. Nuclear option: ./scripts/localstack-dev.sh fresh-start")
        print("=" * 70 + "\n")


# Pytest hook to add custom markers
def pytest_configure(config):
    """Register custom markers for LocalStack tests."""
    config.addinivalue_line(
        "markers",
        "localstack: mark test as requiring LocalStack"
    )
    config.addinivalue_line(
        "markers",
        "state_sync: mark test as requiring state synchronization"
    )
    config.addinivalue_line(
        "markers",
        "fresh_state: mark test as requiring fresh LocalStack state"
    )


# Example usage in tests:
"""
# tests/test_infrastructure.py

import pytest

@pytest.mark.localstack
def test_s3_bucket_creation(localstack_endpoint):
    '''Test S3 bucket creation in LocalStack.'''
    import boto3

    s3 = boto3.client("s3", endpoint_url=localstack_endpoint)

    # Create bucket
    s3.create_bucket(Bucket="test-bucket")

    # Verify
    buckets = s3.list_buckets()
    assert any(b["Name"] == "test-bucket" for b in buckets["Buckets"])


@pytest.mark.state_sync
def test_pulumi_deployment(localstack_state_sync):
    '''Test that Pulumi deployment works with state sync.'''
    import pulumi.automation as auto

    # State is automatically synced before this test
    stack = auto.select_stack(stack_name="dev")
    up_result = stack.up()

    assert up_result.summary.result == "succeeded"
    # State is automatically synced after this test


@pytest.mark.fresh_state
def test_clean_deployment(fresh_localstack):
    '''Test deployment in completely fresh environment.'''
    # LocalStack has been restarted, Pulumi state is empty
    # Perfect for testing deployment from scratch
    ...
"""
