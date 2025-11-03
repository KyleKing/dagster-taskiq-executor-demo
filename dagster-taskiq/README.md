# Dagster TaskIQ

A Dagster executor using TaskIQ and AWS SQS for distributed job execution with exactly-once semantics and auto-scaling.

## Overview

`dagster-taskiq` is a modern replacement for `dagster-celery` that provides:

- **AWS Native**: SQS broker with ECS worker auto-scaling
- **Exactly-Once**: PostgreSQL idempotency storage prevents duplicate execution
- **Cloud Integration**: Native CloudWatch monitoring and AWS IAM security
- **Cost Efficient**: Pay-per-use SQS and ECS Fargate pricing

## Installation

```bash
pip install dagster-taskiq
```

## Quick Start

### Basic Configuration

```python
from dagster import job, op
from dagster_taskiq import taskiq_executor

@op
def process_data():
    return "processed"

@job(executor_def=taskiq_executor.configured({
    "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue",
    "aws_region": "us-east-1",
}))
def my_job():
    process_data()
```

### Repository Configuration

```python
from dagster import repository
from dagster_taskiq import taskiq_executor

@repository
def my_repo():
    return [my_job]
```

### Worker Management

```bash
# Start workers (typically run in ECS)
dagster-taskiq worker --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/my-queue

# Or use the demo application for local development
cd dagster-taskiq-demo
python -m dagster dev
```

## Configuration

### Executor Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `queue_url` | str | Required | SQS queue URL |
| `aws_region` | str | "us-east-1" | AWS region |
| `visibility_timeout` | int | 300 | SQS message visibility timeout (seconds) |
| `message_retention` | int | 1209600 | SQS message retention (seconds) |
| `max_receive_count` | int | 5 | Max receive count before DLQ |
| `idempotency_key_ttl` | int | 86400 | Idempotency record TTL (seconds) |

### AWS IAM Requirements

Workers need these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:GetQueueAttributes"
            ],
            "Resource": "arn:aws:sqs:*:*:*"
        },
        {
            "Effect": "Allow", 
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:*:*:*"
        }
    ]
}
```

## Architecture

### Components

1. **Executor**: Submits Dagster steps to SQS as TaskIQ tasks
1. **Worker**: Consumes SQS messages and executes Dagster steps
1. **Idempotency Storage**: PostgreSQL table prevents duplicate execution
1. **Auto-scaling**: ECS service scales based on SQS queue depth

### Execution Flow

1. Dagster executor creates `OpExecutionTask` payload
1. Task submitted to SQS with unique idempotency key
1. Worker receives message, checks idempotency storage
1. If not executed, runs Dagster step and records completion
1. Executor polls idempotency storage for completion status

### Exactly-Once Semantics

- Each task gets unique idempotency key (`run_id:step_key`)
- Workers check PostgreSQL before execution
- Completed tasks stored in `dagster_taskiq_task_completions`
- SQS visibility timeout handles worker crashes
- Dead-letter queue for failed tasks

## Development

### Local Development

Use the demo application for local development:

```bash
cd dagster-taskiq-demo
# Follow demo README for setup
python -m dagster dev
```

### Testing

```bash
cd dagster-taskiq
mise run test
mise run lint
mise run typecheck
```

### Package Development

```bash
# Install in development mode
pip install -e .

# Build package
python -m build

# Run integration tests
pytest tests/integration/
```

## Migration from Celery

See the main project repository for:

- [Migration Guide](../dagster-celery/README_MIGRATION.md)
- [Migration Status](../dagster-celery/MIGRATION_STATUS.md)
- [Performance Comparisons](../dagster-taskiq-demo/README.md)

## Production Deployment

### ECS Deployment

Recommended production setup using ECS Fargate:

```yaml
# Example ECS task definition
{
    "family": "dagster-taskiq-worker",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "256",
    "memory": "512",
    "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
    "taskRoleArn": "arn:aws:iam::account:role/dagsterTaskiqWorkerRole",
    "containerDefinitions": [
        {
            "name": "worker",
            "image": "your-registry/dagster-taskiq:latest",
            "environment": [
                {"name": "DAGSTER_TASKIQ_QUEUE_URL", "value": "your-sqs-queue-url"}
            ],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/aws/ecs/dagster-taskiq",
                    "awslogs-region": "us-east-1",
                    "awslogs-stream-prefix": "ecs"
                }
            }
        }
    ]
}
```

### Auto-scaling Configuration

Configure ECS auto-scaling based on SQS queue depth:

- Target: 5 messages per worker
- Scale out: When queue depth > 50 messages
- Scale in: When queue depth < 10 messages
- Cooldown: 300 seconds

## Monitoring

### CloudWatch Metrics

- `ApproximateNumberOfMessagesVisible`: Queue depth
- \`ApproximateAgeOfOldestMessage: Processing lag
- `NumberOfMessagesReceived`: Throughput
- `NumberOfMessagesDeleted`: Success rate

### Dagster Integration

- Step execution events in Dagster UI
- Worker health checks via ECS service health
- Error tracking through Dagster run logs

## License

Apache License 2.0
