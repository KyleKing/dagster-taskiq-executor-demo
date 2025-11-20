# Dagster TaskIQ Executor

A Dagster executor implementation using TaskIQ and AWS SQS for distributed job execution. Direct migration from the dagster-celery executor with improved async support and SQS-based task distribution.

## Status

**Experimental** - This executor is under active development with known limitations. See:
- [IMPLEMENTATION_PROGRESS.md](./IMPLEMENTATION_PROGRESS.md) - Current roadmap and progress
- [PARITY_REVIEW.md](./PARITY_REVIEW.md) - Feature parity analysis with dagster-celery

### Known Limitations

- **Queue routing not implemented** - All tasks route to single queue (ignoring `DAGSTER_TASKIQ_QUEUE_TAG`)
- **Priority inversion bug** - Higher priority may cause longer delays
- **Cancellation not supported** - Cannot terminate running jobs
- **Worker health checks return UNKNOWN** - Health monitoring not functional

See [PARITY_REVIEW.md](./PARITY_REVIEW.md) for complete list of gaps vs dagster-celery.

## Installation

```bash
pip install dagster-taskiq
```

### Optional Dependencies

```bash
# For cancellation support (experimental, Phase 3)
pip install dagster-taskiq[cancellation]
```

## Requirements

- Python 3.11+
- Dagster 1.5+
- TaskIQ 0.11+
- AWS SQS (or LocalStack for development)
- PostgreSQL (for idempotency storage)

## Quick Start

### 1. Configure Dagster Instance

Add to your `dagster.yaml`:

```yaml
run_launcher:
  module: dagster_taskiq
  class: TaskiqRunLauncher
  config:
    queue_url: "https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks"
    region_name: "us-east-1"
    # Optional: endpoint_url for LocalStack
    endpoint_url: "http://localhost:4566"

execution:
  config:
    executor:
      config:
        queue_url: "https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks"
        region_name: "us-east-1"
        # Optional: endpoint_url for LocalStack
        endpoint_url: "http://localhost:4566"
```

### 2. Start Workers

```bash
# Start TaskIQ workers
dagster-taskiq worker start \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks \
  --region us-east-1
```

### 3. Run Jobs

Jobs will automatically execute on the worker pool:

```python
from dagster import job, op

@op
def my_op():
    return "Hello from TaskIQ worker!"

@job(executor_def=taskiq_executor)
def my_job():
    my_op()
```

## Configuration

### Executor Configuration

Available configuration options for the executor:

```yaml
execution:
  config:
    executor:
      config:
        queue_url: string           # Required: SQS queue URL
        region_name: string          # Required: AWS region
        endpoint_url: string         # Optional: For LocalStack/custom endpoints
        s3_bucket_name: string       # Optional: S3 bucket for large payloads
        s3_result_backend: string    # Optional: S3 backend for results
        is_fair_queue: boolean       # Optional: Use FIFO queue MessageGroupId
```

### Run Launcher Configuration

```yaml
run_launcher:
  module: dagster_taskiq
  class: TaskiqRunLauncher
  config:
    queue_url: string           # Required: SQS queue URL
    region_name: string          # Required: AWS region
    endpoint_url: string         # Optional: For LocalStack
    default_queue: string        # Optional: Default queue name (not yet implemented)
```

### Worker Configuration

```bash
dagster-taskiq worker start \
  --queue-url <SQS_QUEUE_URL> \
  --region <AWS_REGION> \
  [--endpoint-url <ENDPOINT>] \
  [--concurrency <NUM_WORKERS>]
```

## Architecture

### Components

- **TaskiqExecutor**: Dagster executor that submits ops to SQS
- **TaskiqRunLauncher**: Dagster run launcher for full job execution
- **Core Execution Loop**: Async worker loop consuming from SQS
- **SQS Broker**: TaskIQ broker using `taskiq-aio-multi-sqs`
- **S3 Backend**: Optional result backend for large payloads

### Execution Flow

1. Dagster daemon launches job via `TaskiqRunLauncher`
2. Executor submits individual ops to SQS queue
3. Workers poll SQS and execute ops asynchronously
4. Results stored in idempotency storage (PostgreSQL)
5. Executor polls for completion

### Priority Handling

Priority mapping (in progress, see IMPLEMENTATION_PROGRESS.md):
- Uses SQS DelaySeconds for priority (0-900 seconds)
- Higher Dagster priority = lower delay
- Default priority (5) = 0 delay
- Known issue: Priority inversion bug exists

### Idempotency

- PostgreSQL-backed idempotency storage
- Exactly-once execution semantics
- Prevents duplicate execution on worker failures

## CLI Commands

```bash
# Start worker
dagster-taskiq worker start --queue-url <URL> --region <REGION>

# Get version info
dagster-taskiq --version

# Worker commands (not yet implemented)
# dagster-taskiq worker status
# dagster-taskiq worker terminate
```

## Development

### Running Tests

```bash
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

## Differences from dagster-celery

### Features Not Yet Implemented

- **Queue routing**: `DAGSTER_TASKIQ_QUEUE_TAG` ignored
- **Task cancellation**: Cannot terminate running tasks
- **Worker health checks**: Always return UNKNOWN status
- **Config source**: `config_source` parameter ignored

### Architecture Differences

- Uses SQS instead of Redis/RabbitMQ
- Async-first implementation with asyncio
- Custom worker implementation (not using TaskIQ's task framework)
- Result polling via idempotency storage instead of result backend

### Configuration Differences

- AWS-specific configuration (queue_url, region_name)
- No broker/backend URLs (uses SQS queue URLs)
- No include/exclude patterns for task discovery

See [PARITY_REVIEW.md](./PARITY_REVIEW.md) for comprehensive comparison.

## Implementation Progress

The executor is being developed in phases:

- **Phase 1**: Stabilize core behavior ✅ Mostly complete
- **Phase 2**: Complete TaskIQ API adoption 🔄 In progress
- **Phase 3**: Implement cancellation ⏸️ Planned

See [IMPLEMENTATION_PROGRESS.md](./IMPLEMENTATION_PROGRESS.md) for detailed status.

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

- SQS DelaySeconds support is unreliable in LocalStack
- Some integration tests may fail with LocalStack
- Use real AWS for production testing

### Priority not working as expected

Known issue - priority inversion bug exists. See PARITY_REVIEW.md and IMPLEMENTATION_PROGRESS.md.

## Example Usage

See the [`example/`](./example/) directory for a complete working example, or [`../dagster-taskiq-demo/`](../dagster-taskiq-demo/) for a full production-like deployment.

## Contributing

1. Read [IMPLEMENTATION_PROGRESS.md](./IMPLEMENTATION_PROGRESS.md) for current priorities
2. Check [PARITY_REVIEW.md](./PARITY_REVIEW.md) for known gaps
3. Run tests: `mise run checks`
4. Follow code style guidelines in root AGENTS.md

## License

See [LICENSE](../LICENSE) file in repository root.

## Related Projects

- [dagster-taskiq-demo](../dagster-taskiq-demo/) - Full demo application with load testing
- [taskiq-aio-multi-sqs](../taskiq-aio-multi-sqs/) - Async SQS broker library
- [taskiq-demo](../taskiq-demo/) - Standalone TaskIQ demo with FastAPI
