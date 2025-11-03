# Dagster-Taskiq: Celery to Taskiq Migration

## ✅ Migration Complete (Core Functionality)

This project has been successfully migrated from Celery to Taskiq with AWS SQS as the message broker using aioboto3.

## What Changed

### Package Name
- **Before**: `dagster-celery`
- **After**: `dagster-taskiq`

### Message Broker
- **Before**: Celery with RabbitMQ/Redis
- **After**: Taskiq with AWS SQS (via aioboto3)

### Executor
- **Before**: `celery_executor`
- **After**: `taskiq_executor`

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

**YAML Configuration:**
```yaml
execution:
  config:
    queue_url: "https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks"
    region_name: "us-east-1"
    endpoint_url: "http://localhost:4566"  # For LocalStack development
```

**Environment Variables:**
```bash
# Required: SQS Queue URL
export DAGSTER_TASKIQ_SQS_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks"

# Optional: AWS Region (defaults to us-east-1)
export AWS_DEFAULT_REGION="us-east-1"

# Optional: Custom endpoint for LocalStack
export DAGSTER_TASKIQ_SQS_ENDPOINT_URL="http://localhost:4566"

# AWS Credentials (standard AWS environment variables)
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

## Architecture

### Message Flow

```
┌─────────┐     ┌───────────────┐     ┌─────────┐     ┌────────────┐
│ Dagster │────>│ Taskiq Broker │────>│ AWS SQS │────>│   Worker   │
└─────────┘     └───────────────┘     └─────────┘     └────────────┘
                                                              │
                                                              ▼
                                                       ┌─────────────┐
                                                       │   Result    │
                                                       │   Backend   │
                                                       └─────────────┘
```

### Key Components

1. **SQSBroker** (`broker.py`)
   - Implements Taskiq's `AsyncBroker` interface
   - Sends messages to SQS via `kick()`
   - Receives messages via long polling in `listen()`
   - Supports message acknowledgment

2. **TaskiqExecutor** (`executor.py`)
   - Replaces `CeleryExecutor`
   - Submits tasks to SQS queue
   - Polls for task completion
   - Handles task results

3. **Core Execution Loop** (`core_execution_loop.py`)
   - Orchestrates task execution
   - Manages task lifecycle
   - Handles errors and interruptions

## Running Workers

### Using Taskiq CLI

```bash
# Start a worker
taskiq worker dagster_taskiq.app:broker

# Start with specific configuration
taskiq worker dagster_taskiq.app:broker \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks \
  --region us-east-1
```

### Using Python

```python
import asyncio
from dagster_taskiq.app import broker

async def run_worker():
    """Run a Taskiq worker."""
    await broker.startup()
    try:
        async for message in broker.listen():
            # Process message
            await message.ack()
    finally:
        await broker.shutdown()

if __name__ == "__main__":
    asyncio.run(run_worker())
```

## Testing

### Run Verification Script

```bash
python verify_migration.py
```

This checks:
- ✅ All imports work
- ✅ Broker can be instantiated
- ✅ Executor can be created
- ✅ App factory works correctly

### LocalStack Development

For local development, use LocalStack to emulate AWS SQS:

```bash
# Start LocalStack
docker run -d -p 4566:4566 localstack/localstack

# Create SQS queue
aws --endpoint-url=http://localhost:4566 sqs create-queue \
  --queue-name dagster-tasks

# Get queue URL
aws --endpoint-url=http://localhost:4566 sqs get-queue-url \
  --queue-name dagster-tasks

# Set environment variable
export DAGSTER_TASKIQ_SQS_ENDPOINT_URL="http://localhost:4566"
export DAGSTER_TASKIQ_SQS_QUEUE_URL="<queue-url-from-above>"
```

## Migration Status

### ✅ Completed
- [x] Dependencies updated (setup.py)
- [x] SQS broker implementation
- [x] Configuration migration
- [x] Task definitions
- [x] Executor implementation
- [x] Core execution loop
- [x] Tags and constants
- [x] Module exports
- [x] Package installation
- [x] Import verification

### 🚧 In Progress / Pending
- [ ] CLI migration (worker management)
- [ ] Launcher migration (run management)
- [ ] Test suite migration
- [ ] Documentation updates
- [ ] Integration tests with LocalStack
- [ ] Production deployment guides

**Overall Progress**: ~60% complete

See [MIGRATION_STATUS.md](MIGRATION_STATUS.md) for detailed status.

## Tags

Taskiq uses different tag names from Celery:

| Purpose | Celery Tag | Taskiq Tag |
|---------|------------|------------|
| Step Priority | `dagster-celery/priority` | `dagster-taskiq/priority` |
| Run Priority | `dagster-celery/run_priority` | `dagster-taskiq/run_priority` |
| Queue Selection | `dagster-celery/queue` | `dagster-taskiq/queue` |
| Task ID | `dagster-celery/task_id` | `dagster-taskiq/task_id` |

## Known Limitations

1. **Task Revocation**: Unlike Celery's `revoke()`, Taskiq doesn't support direct task cancellation. On interruption, tasks continue but results are not processed.

2. **Worker Hostname**: Celery provided worker hostname in task context. Taskiq implementation uses placeholder "taskiq-worker".

3. **Async/Sync Bridge**: Dagster's executor interface is synchronous while Taskiq is async-native. Event loops are created/closed for each operation which may have performance implications.

## Performance Considerations

### SQS Characteristics
- **Message Size**: Max 256 KB (consider using S3 for larger payloads)
- **Visibility Timeout**: Default 5 minutes (configurable)
- **Long Polling**: Reduces empty responses, improves efficiency
- **Throughput**: Standard queues provide nearly unlimited throughput

### Optimization Tips
1. Use FIFO queues for strict ordering requirements
2. Batch message processing when possible
3. Monitor SQS metrics (ApproximateNumberOfMessages, etc.)
4. Configure appropriate visibility timeout for your workloads

## Troubleshooting

### Import Errors
```python
# If you see: ModuleNotFoundError: No module named 'dagster_shared'
# Solution: Install dependencies
pip install -e .
```

### SQS Connection Issues
```python
# Check AWS credentials
aws sts get-caller-identity

# Verify queue exists
aws sqs list-queues

# Test endpoint URL (for LocalStack)
curl http://localhost:4566/_localstack/health
```

### Task Not Executing
1. Check queue URL is correct
2. Verify worker is running and connected to same queue
3. Check AWS credentials have SQS permissions
4. Monitor SQS CloudWatch metrics

## Contributing

When migrating remaining components (CLI, launcher, tests):

1. Follow the existing pattern of async/sync bridging
2. Update tag names from `celery` to `taskiq`
3. Replace Celery concepts with Taskiq equivalents
4. Add tests for new functionality
5. Update documentation

## Resources

- [Taskiq Documentation](https://taskiq-python.github.io/)
- [AWS SQS Documentation](https://docs.aws.amazon.com/sqs/)
- [aioboto3 Documentation](https://aioboto3.readthedocs.io/)
- [Dagster Documentation](https://docs.dagster.io/)

## License

Apache License 2.0 (same as original dagster-celery)

## Support

For issues or questions:
1. Check [MIGRATION_STATUS.md](MIGRATION_STATUS.md) for known issues
2. Review verification script output: `python verify_migration.py`
3. Check SQS queue status and CloudWatch logs
4. Ensure all environment variables are set correctly

---

**Note**: This migration provides core functionality. CLI and launcher components are pending and should be migrated before production use.
