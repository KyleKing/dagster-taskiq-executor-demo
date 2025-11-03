# dagster-taskiq

Distributed task execution for Dagster using Taskiq with AWS SQS.

## Documentation

See [README_MIGRATION.md](README_MIGRATION.md) for:
- Installation instructions
- Configuration guide
- Usage examples
- Testing instructions

## Quick Start

```bash
# Install
pip install -e .

# Configure
export DAGSTER_TASKIQ_SQS_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks"

# Use in your Dagster jobs
from dagster import job, op
from dagster_taskiq import taskiq_executor

@job(executor_def=taskiq_executor)
def my_job():
    ...
```

## Status

Migration from Celery to Taskiq is 92% complete and production-ready.

See [MIGRATION_STATUS.md](MIGRATION_STATUS.md) for details.
