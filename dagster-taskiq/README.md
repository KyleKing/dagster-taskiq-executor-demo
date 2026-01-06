# Dagster TaskIQ Executor

A Dagster executor implementation using TaskIQ with AWS SQS for distributed task execution.

## Overview

This package provides a TaskIQ-based executor for Dagster that uses AWS SQS for task distribution and S3 for result storage.

## Features

- **Single Queue Architecture**: All tasks go to a single SQS queue
- **FIFO Queue Support**: Automatic detection and configuration of FIFO queues
- **S3 Result Backend**: Results stored in S3 with support for extended payloads (>256KB)

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

FIFO queues are automatically detected by the `.fifo` suffix:

```yaml
execution:
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks.fifo'
```

### S3 Extended Payloads

For messages larger than 256KB:

```yaml
execution:
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
    config_source:
      s3_bucket_name: 'my-taskiq-bucket'
```

### Advanced Configuration

```yaml
execution:
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
    config_source:
      wait_time_seconds: 20
      max_number_of_messages: 1
      use_task_id_for_deduplication: false
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

## Development

### Running Tests

```bash
cd dagster-taskiq
mise run :test
```

## Known Limitations

- **Multi-queue routing**: Not supported (all tasks go to single queue)
- **Priority-based delays**: Not supported
- **Run termination**: Not supported
- **Worker health checks**: Not supported (returns UNKNOWN)
- **Cancellation**: Not implemented

## License

Apache-2.0
