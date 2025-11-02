# dagster-taskiq

A Dagster executor that uses TaskIQ and SQS for distributed job execution.

## Overview

`dagster-taskiq` is a derivative of `dagster-celery` that replaces Celery with TaskIQ workers backed by SQS for improved scalability and exactly-once execution semantics.

## Installation

```bash
pip install dagster-taskiq
```

## Usage

### Executor Configuration

In your Dagster repository, configure the TaskIQ executor:

```python
from dagster import repository
from dagster_taskiq import taskiq_executor

@repository
def my_repo():
    return [
        # ... your jobs
    ]

# Configure executor in your job or at repository level
@job(executor_def=taskiq_executor.configured({
    "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue",
    "aws_region": "us-east-1",
    # ... other AWS config
}))
def my_job():
    # ... your ops
```

### Running Workers

Start TaskIQ workers to process jobs:

```bash
dagster-taskiq --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/my-queue
```

## Development

This package is in early development. See the main project repository for LocalStack demo and development setup.

## License

Apache License 2.0