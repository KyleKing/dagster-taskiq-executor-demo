# Dagster TaskIQ Example

This directory contains a complete example demonstrating how to use Dagster with TaskIQ execution on AWS SQS (via LocalStack for local development).

## Overview

This example showcases:

- **Dagster Integration**: Full Dagster setup with PostgreSQL storage, daemon, and web UI
- **TaskIQ Execution**: Distributed job execution using AWS SQS as the message broker
- **LocalStack**: Local AWS service emulation for SQS and S3
- **Multiple Workers**: Two worker containers demonstrating distributed execution
- **Example Jobs**: Includes both partitioned asset jobs and simple op-based jobs

## Architecture

The example uses Docker Compose to orchestrate:

- **PostgreSQL**: Dagster metadata storage
- **LocalStack**: AWS service emulation (SQS, S3)
- **Code Location**: gRPC server hosting the Dagster definitions
- **Workers** (2): TaskIQ workers processing jobs from SQS
- **Webserver**: Dagster UI (http://localhost:3000)
- **Daemon**: Dagster daemon for scheduled runs

## Prerequisites

- Docker and Docker Compose
- AWS CLI (for queue initialization, optional)

## Quick Start

### 1. Initialize AWS Resources

Before starting the services, you need to create the SQS queues and S3 bucket in LocalStack. You can do this manually or use the provided script:

**Option A: Using the initialization script** (recommended)

```bash
cd docker
./init-queues.sh
```

**Option B: Manual initialization**

After LocalStack is running, create the resources:

```bash
# Start LocalStack first
docker compose up -d localstack

# Wait for LocalStack to be ready, then create queues
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name dagster-tasks
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name dagster-tasks-cancels

# Create S3 bucket
aws --endpoint-url=http://localhost:4566 s3 mb s3://dagster-taskiq-results
```

### 2. Start Services

Start all services using Docker Compose:

```bash
docker compose --profile dagster up -d
```

This will start:
- PostgreSQL database
- LocalStack (SQS, S3)
- Code location (gRPC server)
- Two TaskIQ workers
- Dagster webserver
- Dagster daemon

### 3. Access the UI

Open the Dagster UI at http://localhost:3000

### 4. Run Jobs

You can run jobs from the UI:

- **`partitioned_job_long`**: A partitioned asset job with 31 partitions
- **`unreliable_job_short`**: A simple job that fails 50% of the time (for testing retries)

## Configuration

### Environment Variables

Configuration is provided via `docker/docker.env`:

- **PostgreSQL**: Database connection settings
- **AWS SQS**: Queue URL and endpoint (LocalStack)
- **AWS S3**: Bucket name and endpoint (LocalStack)
- **AWS Credentials**: Test credentials for LocalStack

### YAML Configuration

- **`docker/dagster.yaml`**: Dagster instance configuration
- **`docker/taskiq.yaml`**: TaskIQ executor configuration
- **`docker/workspace.yaml`**: Workspace definition pointing to the code location

## Example Jobs

### `partitioned_job_long`

A partitioned asset job with 31 partitions. Each partition runs independently and takes approximately 10 seconds.

### `unreliable_job_short`

A simple job with three ops (`start` → `unreliable` → `end`) that fails 50% of the time. Useful for testing retry logic and error handling.

## Known Limitations

### Single Queue Implementation

All tasks are sent to a single SQS queue. Multi-queue routing and priority-based scheduling have been removed to simplify the implementation.

## Troubleshooting

### Workers Not Processing Tasks

1. **Check queue exists**: Verify the SQS queue was created in LocalStack
   ```bash
   aws --endpoint-url=http://localhost:4566 sqs list-queues
   ```

2. **Check worker logs**: View worker logs to see if they're connecting
   ```bash
   docker compose logs worker-short
   docker compose logs worker-long
   ```

3. **Verify environment variables**: Ensure `docker/docker.env` has correct values

### LocalStack Connection Issues

- Ensure LocalStack is running: `docker compose ps localstack`
- Check LocalStack logs: `docker compose logs localstack`
- Verify endpoint URL: Should be `http://localstack:4566` from within containers

### Database Connection Issues

- Ensure PostgreSQL is running: `docker compose ps postgresql`
- Check PostgreSQL logs: `docker compose logs postgresql`
- Verify connection string in `docker/docker.env`

### Jobs Not Appearing in UI

1. Check code location container is running: `docker compose ps codelocation`
2. Check code location logs: `docker compose logs codelocation`
3. Verify workspace configuration in `docker/workspace.yaml`

## Development

### Building the Image

The Docker image is built automatically when you start services. To rebuild:

```bash
docker compose build codelocation
```

### Modifying Definitions

Edit `src/dagster_taskiq_example/definitions.py` and restart the code location:

```bash
docker compose restart codelocation
```

### Viewing Logs

View logs for all services:

```bash
docker compose logs -f
```

View logs for a specific service:

```bash
docker compose logs -f worker-short
docker compose logs -f webserver
docker compose logs -f daemon
```

## Stopping Services

Stop all services:

```bash
docker compose --profile dagster down
```

Remove volumes (cleans up database and LocalStack data):

```bash
docker compose --profile dagster down -v
```

## Additional Resources

- [Dagster Documentation](https://docs.dagster.io/)
- [TaskIQ Documentation](https://taskiq-python.github.io/)
- [LocalStack Documentation](https://docs.localstack.cloud/)
- [Parity Review](../PARITY_REVIEW.md) - Known differences from dagster-celery

