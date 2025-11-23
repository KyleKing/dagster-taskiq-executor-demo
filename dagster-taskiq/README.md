# Dagster TaskIQ Executor

A Dagster executor implementation using TaskIQ with AWS SQS for distributed task execution.

## Overview

This package provides a TaskIQ-based executor for Dagster that uses AWS SQS for task distribution and S3 for result storage. It's a direct migration from the Dagster-Celery implementation, simplified to use a single SQS queue with TaskIQ's native APIs.

## Features

- **Single Queue Architecture**: Simplified to a single SQS queue (no multi-queue routing)
- **FIFO Queue Support**: Automatic detection and configuration of FIFO queues
- **S3 Result Backend**: Results stored in S3 with support for extended payloads (>256KB)
- **Cancellation Support**: ✅ Fully implemented - Workers check cancellation queue and cancel tasks
- **Worker Health Checks**: ✅ Implemented - Uses result backend to check task status
- **LocalStack Compatible**: Works with LocalStack for local development and testing

## Installation

```bash
pip install dagster-taskiq
```

## Requirements

- Python 3.11+
- Dagster 1.5+
- TaskIQ 0.11+
- AWS SQS (or LocalStack for development)
- AWS S3 for result storage

## Configuration

### Basic Configuration

```yaml
execution:
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
    region_name: 'us-east-1'
    endpoint_url: 'http://localhost:4566'  # Optional, for LocalStack
```

### Run Launcher Configuration

```yaml
run_launcher:
  module: dagster_taskiq
  class: TaskiqRunLauncher
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
    region_name: 'us-east-1'
    endpoint_url: 'http://localhost:4566'  # Optional, for LocalStack
```

### FIFO Queue Configuration

FIFO queues are automatically detected by the `.fifo` suffix in the queue URL. The `is_fair_queue` option is automatically set based on queue type:

```yaml
execution:
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks.fifo'
    # is_fair_queue is automatically set to True for FIFO queues
```

You can explicitly set `is_fair_queue` in `config_source`, but it will be ignored (with a warning) if the queue URL is not FIFO:

```yaml
execution:
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
    config_source:
      is_fair_queue: true  # Warning: ignored for non-FIFO queues
```

### S3 Extended Payloads

For messages larger than 256KB, configure S3 extended payload support:

```yaml
execution:
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
    config_source:
      s3_bucket_name: 'my-taskiq-bucket'  # Used for both results and extended payloads
      s3_endpoint_url: 'http://localhost:4566'  # Optional, for LocalStack
```

The S3 bucket is automatically used for extended payloads when configured.

### Cancellation

Cancellation support can be enabled via environment variable or config:

```bash
export DAGSTER_TASKIQ_ENABLE_CANCELLATION=1
```

Or in config:

```yaml
execution:
  config:
    config_source:
      enable_cancellation: true
```

When enabled, the system uses a separate SQS queue (named `{queue-name}-cancels`) for cancellation messages. Workers automatically listen for cancellation requests and cancel running tasks when requested.

**Note**: Cancellation requires both the executor and workers to have cancellation enabled. The cancel queue must be created manually (see `CANCELLATION.md` for details).

For comprehensive cancellation documentation, troubleshooting, and examples, see [`CANCELLATION.md`](CANCELLATION.md).

### Advanced Configuration

Additional broker options can be passed via `config_source`:

```yaml
execution:
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
    config_source:
      wait_time_seconds: 20
      max_number_of_messages: 1
      use_task_id_for_deduplication: false
      extra_options: {}
```

## Usage

### Basic Job Definition

```python
from dagster import job, op
from dagster_taskiq import taskiq_executor

@op
def my_op():
    return "Hello from TaskIQ worker!"

@job(executor_def=taskiq_executor)
def my_taskiq_job():
    my_op()
```

### Running Workers

Start TaskIQ workers using the CLI:

```bash
dagster-taskiq worker start
```

Or programmatically:

```python
from dagster_taskiq.cli import worker_start_command
worker_start_command(args)
```

### CLI Commands

```bash
# Start worker
dagster-taskiq worker start

# Get version info
dagster-taskiq --version
```

## Development

### Running Tests

```bash
cd dagster-taskiq
mise run test           # Run all tests
mise run test -- -v     # Verbose output
mise run test -- -k "test_name"  # Run specific test
```

### Code Quality

```bash
mise run lint           # Check code style
mise run lint --fix     # Auto-fix issues
mise run format         # Format code
mise run typecheck      # Type checking
mise run checks         # All checks
```

### LocalStack Setup

For local development, use LocalStack:

```bash
# Start LocalStack (see docker-compose.yml)
docker-compose up -d localstack

# Set environment variables
export DAGSTER_TASKIQ_SQS_ENDPOINT_URL=http://localhost:4566
export DAGSTER_TASKIQ_S3_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

## Architecture

### Components

- **TaskiqExecutor**: Dagster executor that submits ops to SQS
- **TaskiqRunLauncher**: Dagster run launcher for full job execution
- **Core Execution Loop**: Async worker loop consuming from SQS
- **SQS Broker**: TaskIQ broker using `taskiq-aio-sqs`
- **S3 Backend**: Result backend for large payloads and task results

### Execution Flow

1. Dagster daemon launches job via `TaskiqRunLauncher`
2. Executor submits individual ops to SQS queue
3. Workers poll SQS and execute ops asynchronously
4. Results stored in S3 result backend
5. Executor polls result backend for completion

## Known Limitations

- **Multi-queue routing**: Not supported (simplified to single queue)
- **Priority-based delays**: Not supported (removed in simplification)
- **LocalStack**: Some SQS features may not work identically to AWS. See [`LOCALSTACK.md`](LOCALSTACK.md) for details and workarounds.

## Migration from Dagster-Celery

Key differences from Dagster-Celery:

### Architecture Changes

- **Single queue**: No multi-queue routing or priority-based delays
- **TaskIQ APIs**: Uses TaskIQ's native broker APIs instead of custom implementations
- **S3 results**: Results stored in S3 (not Redis)
- **Cancellation**: Uses SQS-based cancellation (not Redis-based)

### Features Removed for Simplicity

- Multi-queue routing via tags (`DAGSTER_TASKIQ_QUEUE_TAG` not supported)
- Priority-based task scheduling with delays
- Redis backend support

### Features Retained/Implemented

- ✅ Task cancellation (SQS-based, fully implemented)
- ✅ Worker health checks (S3 result backend-based)
- ✅ FIFO queue support with automatic detection
- ✅ Extended message support (S3-backed for >256KB)

## Troubleshooting

### Workers not processing tasks

1. Verify SQS queue exists and is accessible
2. Check worker logs for connection errors
3. Verify AWS credentials are configured
4. For LocalStack: ensure endpoint_url is set correctly

### Tasks failing with "not found" errors

1. Ensure worker can import your Dagster code
2. Verify PYTHONPATH includes your project
3. Check worker logs for import errors

### LocalStack integration issues

- Some SQS features may not work identically to AWS
- See [`LOCALSTACK.md`](LOCALSTACK.md) for known issues and workarounds
- Use real AWS for production testing

### Cancellation not working

- Ensure cancellation is enabled in both executor and worker configuration
- Verify the cancel queue exists (named `{queue-name}-cancels`)
- See [`CANCELLATION.md`](CANCELLATION.md) for detailed troubleshooting

## Example Usage

See the [`example/`](./example/) directory for a complete working example, or [`../dagster-taskiq-demo/`](../dagster-taskiq-demo/) for a full production-like deployment.

## Contributing

1. Run tests: `mise run checks`
2. Follow code style guidelines in root AGENTS.md
3. See [`../TODO.md`](../TODO.md) for current priorities

## License

Apache-2.0

## Related Projects

- [dagster-taskiq-demo](../dagster-taskiq-demo/) - Full demo application with load testing
- [taskiq-demo](../taskiq-demo/) - Standalone TaskIQ demo with FastAPI
- [taskiq-aio-sqs](https://github.com/taskiq-python/taskiq-aio-sqs) - Async SQS broker library (external dependency)
