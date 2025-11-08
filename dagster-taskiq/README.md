# Dagster TaskIQ Executor

A Dagster executor implementation using TaskIQ with AWS SQS for distributed task execution.

## Overview

This package provides a TaskIQ-based executor for Dagster that uses AWS SQS for task distribution and S3 for result storage. It's a direct migration from the Dagster-Celery implementation, simplified to use a single SQS queue with TaskIQ's native APIs.

## Features

- **Single Queue Architecture**: Simplified to a single SQS queue (no multi-queue routing)
- **FIFO Queue Support**: Automatic detection and configuration of FIFO queues
- **S3 Result Backend**: Results stored in S3 with support for extended payloads (>256KB)
- **Cancellation Support**: Infrastructure for task cancellation (worker-side implementation pending)
- **LocalStack Compatible**: Works with LocalStack for local development and testing

## Installation

```bash
pip install dagster-taskiq
```

## Configuration

### Basic Configuration

```yaml
execution:
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

**Note**: Cancellation requires both the executor and workers to have cancellation enabled. The cancel queue is automatically created with the naming convention `{main-queue-name}-cancels`.

### Advanced Configuration

Additional broker options can be passed via `config_source`:

```yaml
execution:
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
    config_source:
      wait_time_seconds: 20
      max_number_of_messages: 1
      delay_seconds: 0
      use_task_id_for_deduplication: false
      extra_options: {}
```

## Usage

### Basic Job Definition

```python
from dagster import job
from dagster_taskiq import taskiq_executor

@job(executor_def=taskiq_executor)
def my_taskiq_job():
    # Your ops here
    pass
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

## Development

### Running Tests

```bash
cd dagster-taskiq
mise run test
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

## Known Limitations

- **Multi-queue routing**: Not supported (simplified to single queue)
- **Priority-based delays**: Not supported (removed in simplification)
- **Worker cancellation**: ✅ Fully implemented - Workers check cancellation queue and cancel tasks
- **Worker health checks**: Returns `UNKNOWN` (result backend status not checked)
- **LocalStack**: Some SQS features may not work identically to AWS (e.g., `DelaySeconds`)

## Migration from Dagster-Celery

Key differences from Dagster-Celery:

1. **Single queue**: No multi-queue routing or priority-based delays
2. **TaskIQ APIs**: Uses TaskIQ's native broker APIs instead of custom implementations
3. **S3 results**: Results stored in S3 (not Redis)
4. **Cancellation**: Uses SQS-based cancellation (not Redis-based)

## License

Apache-2.0
