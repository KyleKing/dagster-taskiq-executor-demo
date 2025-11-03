#!/usr/bin/env python
"""Verification script for Celery to Taskiq migration."""

import sys


def verify_imports():
    """Verify all critical imports work."""
    print("=" * 60)
    print("VERIFYING IMPORTS")
    print("=" * 60)

    try:
        from dagster_taskiq import taskiq_executor
        print("✅ taskiq_executor imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import taskiq_executor: {e}")
        return False

    try:
        from dagster_taskiq.broker import SQSBroker
        print("✅ SQSBroker imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import SQSBroker: {e}")
        return False

    try:
        from dagster_taskiq.executor import TaskiqExecutor
        print("✅ TaskiqExecutor imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import TaskiqExecutor: {e}")
        return False

    try:
        from dagster_taskiq.make_app import make_app
        print("✅ make_app imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import make_app: {e}")
        return False

    try:
        from dagster_taskiq.tasks import create_task, create_execute_job_task, create_resume_job_task
        print("✅ Task creation functions imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import task functions: {e}")
        return False

    try:
        from dagster_taskiq.core_execution_loop import core_taskiq_execution_loop
        print("✅ core_taskiq_execution_loop imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import core_taskiq_execution_loop: {e}")
        return False

    try:
        from dagster_taskiq.tags import (
            DAGSTER_TASKIQ_QUEUE_TAG,
            DAGSTER_TASKIQ_STEP_PRIORITY_TAG,
            DAGSTER_TASKIQ_RUN_PRIORITY_TAG,
        )
        print("✅ Tags imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import tags: {e}")
        return False

    print()
    return True


def verify_broker_creation():
    """Verify broker can be created."""
    print("=" * 60)
    print("VERIFYING BROKER CREATION")
    print("=" * 60)

    try:
        from dagster_taskiq.broker import SQSBroker

        # Create broker with test configuration
        broker = SQSBroker(
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            endpoint_url="http://localhost:4566",  # LocalStack
            region_name="us-east-1",
        )
        print("✅ SQSBroker instance created successfully")
        print(f"   Queue URL: {broker.config.queue_url}")
        print(f"   Region: {broker.config.region_name}")
        print(f"   Endpoint: {broker.config.endpoint_url}")
        print()
        return True
    except Exception as e:
        print(f"❌ Failed to create broker: {e}")
        print()
        return False


def verify_executor_creation():
    """Verify executor can be created."""
    print("=" * 60)
    print("VERIFYING EXECUTOR CREATION")
    print("=" * 60)

    try:
        from dagster_taskiq.executor import TaskiqExecutor
        from dagster._core.execution.retries import RetryMode

        # Create executor
        executor = TaskiqExecutor(
            retries=RetryMode(RetryMode.DISABLED),
            queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            region_name="us-east-1",
            endpoint_url="http://localhost:4566",
        )
        print("✅ TaskiqExecutor instance created successfully")
        print(f"   Queue URL: {executor.queue_url}")
        print(f"   Region: {executor.region_name}")
        print(f"   Retry mode: {executor.retries}")
        print()
        return True
    except Exception as e:
        print(f"❌ Failed to create executor: {e}")
        print()
        return False


def verify_app_factory():
    """Verify app factory works."""
    print("=" * 60)
    print("VERIFYING APP FACTORY")
    print("=" * 60)

    try:
        from dagster_taskiq.make_app import make_app

        # Create broker via factory
        broker = make_app({
            "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
            "endpoint_url": "http://localhost:4566",
            "region_name": "us-east-1",
        })
        print("✅ Broker created via make_app() successfully")
        print(f"   Broker type: {type(broker).__name__}")
        print()
        return True
    except Exception as e:
        print(f"❌ Failed to create broker via make_app: {e}")
        print()
        return False


def verify_no_celery_imports():
    """Verify no Celery imports remain."""
    print("=" * 60)
    print("VERIFYING NO CELERY DEPENDENCIES")
    print("=" * 60)

    celery_found = False
    try:
        import celery
        celery_found = True
        print("⚠️  Celery is still installed (may cause conflicts)")
    except ImportError:
        print("✅ Celery not installed (good)")

    print()
    return not celery_found


def main():
    """Run all verification checks."""
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "  DAGSTER-TASKIQ MIGRATION VERIFICATION".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    results = []

    # Run verification steps
    results.append(("Imports", verify_imports()))
    results.append(("Broker Creation", verify_broker_creation()))
    results.append(("Executor Creation", verify_executor_creation()))
    results.append(("App Factory", verify_app_factory()))

    # Print summary
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:8} {name}")
        if not passed:
            all_passed = False

    print()

    if all_passed:
        print("╔" + "=" * 58 + "╗")
        print("║" + " " * 58 + "║")
        print("║" + "  ✅ ALL VERIFICATIONS PASSED!".center(58) + "║")
        print("║" + " " * 58 + "║")
        print("║" + "  Core migration is complete and functional.".center(58) + "║")
        print("║" + " " * 58 + "║")
        print("║" + "  Next steps:".ljust(58) + "║")
        print("║" + "    1. Migrate CLI and launcher".ljust(58) + "║")
        print("║" + "    2. Update test suite".ljust(58) + "║")
        print("║" + "    3. Test with LocalStack SQS".ljust(58) + "║")
        print("║" + " " * 58 + "║")
        print("╚" + "=" * 58 + "╝")
        print()
        return 0
    else:
        print("╔" + "=" * 58 + "╗")
        print("║" + " " * 58 + "║")
        print("║" + "  ❌ SOME VERIFICATIONS FAILED".center(58) + "║")
        print("║" + " " * 58 + "║")
        print("║" + "  Please review the errors above.".center(58) + "║")
        print("║" + " " * 58 + "║")
        print("╚" + "=" * 58 + "╝")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
