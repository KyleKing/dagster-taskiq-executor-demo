"""Integration test configuration using Pulumi Automation API.

This module provides pytest fixtures for deploying real infrastructure
to LocalStack and running integration tests against it.

Following pulumi-testing skill guidance:
- 70% integration tests (real infrastructure)
- 20% property tests (deployment-time validation)
- 10% unit tests (mocking only when necessary)
"""

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Generator

import boto3
import pytest
from pulumi import automation as auto

# Add skills scripts to path for LocalStack sync utilities
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Import LocalStack sync fixtures
try:
    from pytest_localstack_sync import (
        ensure_localstack,
        fresh_localstack,
        localstack_endpoint,
        localstack_state_sync,
    )
except ImportError:
    # Define minimal versions if import fails
    @pytest.fixture(scope="session")
    def localstack_endpoint():
        return "http://localhost:4566"

    @pytest.fixture(scope="session", autouse=True)
    def ensure_localstack():
        # Assume LocalStack is running
        yield


# Re-export so tests can use them
__all__ = [
    "ensure_localstack",
    "localstack_endpoint",
    "localstack_state_sync",
    "fresh_localstack",
    "pulumi_stack",
    "boto3_clients",
]


@pytest.fixture(scope="module")
def pulumi_stack(localstack_endpoint: str) -> Generator[dict[str, Any], None, None]:
    """Deploy ephemeral Pulumi stack for integration testing.

    This fixture:
    1. Creates a unique test stack
    2. Deploys infrastructure to LocalStack
    3. Yields stack and outputs to tests
    4. Destroys infrastructure after tests
    5. Cleans up the stack

    Scope: module - shared across all tests in a module for efficiency
    """
    # Generate unique stack name to avoid conflicts
    stack_name = f"test-{uuid.uuid4().hex[:8]}"
    project_name = "localstack-ecs-sqs"
    work_dir = str(Path(__file__).parent.parent)

    print(f"\n=== Deploying test stack: {stack_name} ===")

    # Create or select stack
    stack = auto.create_or_select_stack(
        stack_name=stack_name,
        project_name=project_name,
        work_dir=work_dir,
    )

    # Configure stack for LocalStack
    stack.set_config("aws:region", auto.ConfigValue("us-east-1"))
    stack.set_config("aws:skipCredentialsValidation", auto.ConfigValue("true"))
    stack.set_config("aws:skipRequestingAccountId", auto.ConfigValue("true"))
    stack.set_config("aws:s3UsePathStyle", auto.ConfigValue("true"))

    # Set project configuration
    stack.set_config("project:name", auto.ConfigValue("dagster-taskiq-demo"))
    stack.set_config("project:environment", auto.ConfigValue(stack_name))

    # Set AWS configuration
    stack.set_config("aws:region", auto.ConfigValue("us-east-1"))
    stack.set_config("aws:endpoint", auto.ConfigValue(localstack_endpoint))
    stack.set_config("aws:accessKey", auto.ConfigValue("test"))
    stack.set_config("aws:secretKey", auto.ConfigValue("test"))

    # Set queue configuration
    stack.set_config("queue:messageRetentionSeconds", auto.ConfigValue("1209600"))
    stack.set_config("queue:visibilityTimeout", auto.ConfigValue("900"))
    stack.set_config("queue:dlqVisibilityTimeout", auto.ConfigValue("300"))
    stack.set_config("queue:redriveMaxReceiveCount", auto.ConfigValue("3"))

    # Set database configuration
    stack.set_config("database:engineVersion", auto.ConfigValue("17"))
    stack.set_config("database:minCapacity", auto.ConfigValue("0.5"))
    stack.set_config("database:maxCapacity", auto.ConfigValue("1.0"))
    stack.set_config("database:username", auto.ConfigValue("dagster"))
    stack.set_config("database:password", auto.ConfigValue("dagster"), secret=True)
    stack.set_config("database:dbName", auto.ConfigValue("dagster"))
    stack.set_config("database:backupRetentionPeriod", auto.ConfigValue("7"))
    stack.set_config("database:deletionProtection", auto.ConfigValue("false"))
    stack.set_config("database:publiclyAccessible", auto.ConfigValue("true"))

    # Set service configuration
    stack.set_config("services:daemonDesiredCount", auto.ConfigValue("1"))
    stack.set_config("services:webserverDesiredCount", auto.ConfigValue("1"))
    stack.set_config("services:workerDesiredCount", auto.ConfigValue("1"))  # Reduced for tests

    # Set taskiq demo configuration
    stack.set_config("taskiqDemo:enabled", auto.ConfigValue("false"))  # Disable for faster tests

    try:
        # Deploy infrastructure
        print("Deploying infrastructure...")
        up_result = stack.up(on_output=lambda msg: print(f"  {msg}"))

        print(f"\n✓ Deployment complete: {up_result.summary.result}")
        print(f"  Resources: {up_result.summary.resource_changes}")

        # Yield stack and outputs to tests
        yield {
            "stack": stack,
            "outputs": up_result.outputs,
            "stack_name": stack_name,
            "endpoint": localstack_endpoint,
        }

    finally:
        # Teardown: destroy infrastructure
        print(f"\n=== Destroying test stack: {stack_name} ===")
        try:
            destroy_result = stack.destroy(on_output=lambda msg: print(f"  {msg}"))
            print(f"✓ Destroy complete: {destroy_result.summary.result}")
        except Exception as e:
            print(f"✗ Destroy failed: {e}")
            print("  Stack may need manual cleanup")

        # Remove stack
        try:
            stack.workspace.remove_stack(stack_name)
            print(f"✓ Stack {stack_name} removed")
        except Exception as e:
            print(f"✗ Failed to remove stack: {e}")


@pytest.fixture
def boto3_clients(
    pulumi_stack: dict[str, Any],
    localstack_endpoint: str,
) -> dict[str, Any]:
    """Create boto3 clients configured for LocalStack.

    Provides clients for testing deployed infrastructure:
    - s3: S3 operations
    - sqs: SQS queue operations
    - ecs: ECS cluster/service operations
    - rds: RDS database operations
    - ec2: VPC and security group operations
    - iam: IAM role/policy operations
    - elbv2: Load balancer operations

    Returns:
        dict: Boto3 clients configured for LocalStack
    """
    # Common client configuration
    config = {
        "endpoint_url": localstack_endpoint,
        "aws_access_key_id": "test",
        "aws_secret_access_key": "test",
        "region_name": "us-east-1",
    }

    return {
        "s3": boto3.client("s3", **config),
        "sqs": boto3.client("sqs", **config),
        "ecs": boto3.client("ecs", **config),
        "rds": boto3.client("rds", **config),
        "ec2": boto3.client("ec2", **config),
        "iam": boto3.client("iam", **config),
        "elbv2": boto3.client("elbv2", **config),
        "logs": boto3.client("logs", **config),
        "servicediscovery": boto3.client("servicediscovery", **config),
    }


@pytest.fixture
def stack_outputs(pulumi_stack: dict[str, Any]) -> dict[str, Any]:
    """Extract and convert stack outputs to dict.

    Returns:
        dict: Stack outputs with resolved values
    """
    outputs = {}
    for key, output in pulumi_stack["outputs"].items():
        outputs[key] = output.value

    return outputs
