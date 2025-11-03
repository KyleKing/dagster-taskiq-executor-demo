# Dagster-Taskiq

Distributed task execution for Dagster using Taskiq with AWS SQS.

## Overview

This project migrates from Celery to Taskiq, providing:

- ✅ Task execution and distribution
- ✅ Worker management (CLI)
- ✅ Run launching and management
- ✅ Priority and queue routing

### What Changed

| Component | Before | After |
|-----------|--------|-------|
| Package | `dagster-celery` | `dagster-taskiq` |
| Broker | Celery with RabbitMQ/Redis | Taskiq with AWS SQS |
| Executor | `celery_executor` | `taskiq_executor` |
| Tags | `dagster-celery/*` | `dagster-taskiq/*` |

## Quick Start

### Installation

```bash
pip install -e .
```

### Basic Usage

```python
from dagster import job, op
from dagster_taskiq import taskiq_executor

@op
def my_operation():
    return "Hello from Taskiq!"

@job(executor_def=taskiq_executor)
def my_job():
    my_operation()
```

### Configuration

**Environment Variables:**

```bash
# Required
export DAGSTER_TASKIQ_SQS_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks"

# Optional
export AWS_DEFAULT_REGION="us-east-1"  # defaults to us-east-1
export DAGSTER_TASKIQ_SQS_ENDPOINT_URL="http://localhost:4566"  # for LocalStack

# AWS Credentials (standard)
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

**YAML Configuration:**

```yaml
execution:
  config:
    queue_url: "https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks"
    region_name: "us-east-1"
    endpoint_url: "http://localhost:4566"  # for LocalStack
```

## Running Workers

### CLI (Recommended)

```bash
# Start a worker
dagster-taskiq worker start

# Start with custom config
dagster-taskiq worker start --config-yaml config.yaml

# Start multiple workers
dagster-taskiq worker start --workers 4

# Check queue status
dagster-taskiq worker list
```

### Taskiq CLI

```bash
taskiq worker dagster_taskiq.app:broker --log-level info --workers 2
```

## Run Launcher

Configure in `dagster.yaml`:

```yaml
run_launcher:
  module: dagster_taskiq
  class: TaskiqRunLauncher
  config:
    queue_url: "https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks"
    region_name: "us-east-1"
    endpoint_url: "http://localhost:4566"  # for LocalStack
    default_queue: "dagster"
```

Or programmatically:

```python
from dagster_taskiq import TaskiqRunLauncher

launcher = TaskiqRunLauncher(
    default_queue="dagster",
    queue_url="https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks",
    region_name="us-east-1",
)
```

## Testing

### Verification

```bash
python verify_migration.py
```

### Unit Tests

```bash
pytest dagster_taskiq_tests/test_cli.py -v
pytest dagster_taskiq_tests/test_config.py -v
pytest dagster_taskiq_tests/test_version.py -v
pytest dagster_taskiq_tests/test_utils.py -v
```

### LocalStack Development

```bash
# Start LocalStack
docker run -d -p 4566:4566 localstack/localstack

# Create queue
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name dagster-tasks

# Get queue URL
aws --endpoint-url=http://localhost:4566 sqs get-queue-url --queue-name dagster-tasks

# Configure
export DAGSTER_TASKIQ_SQS_ENDPOINT_URL="http://localhost:4566"
export DAGSTER_TASKIQ_SQS_QUEUE_URL="<queue-url>"
```

## Known Limitations

1. **Task Revocation**: Taskiq doesn't support direct task cancellation like Celery's `revoke()`. Tasks continue on interruption but results aren't processed.

1. **Worker Hostname**: Uses placeholder "taskiq-worker" instead of actual hostname.

1. **Async/Sync Bridge**: Event loops created/closed per operation may impact performance.

## Troubleshooting

### Import Errors

```bash
pip install -e .
```

### SQS Connection

```bash
# Check credentials
aws sts get-caller-identity

# Verify queue
aws sqs list-queues

# Test LocalStack
curl http://localhost:4566/_localstack/health
```

### Task Not Executing

- Verify queue URL is correct
- Check worker is running
- Confirm AWS credentials have SQS permissions
- Monitor CloudWatch metrics

## Resources

- [Taskiq Documentation](https://taskiq-python.github.io/)
- [AWS SQS Documentation](https://docs.aws.amazon.com/sqs/)
- [aioboto3 Documentation](https://aioboto3.readthedocs.io/)
- [Dagster Documentation](https://docs.dagster.io/)

## License

Apache License 2.0
