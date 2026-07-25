# Dagster TaskIQ Executor

> [!WARNING]
> This was a really insightful and interesting side-project to get a better understanding of Dagster and TaskIQ, but [Hatchet](https://hatchet.run) is the all around better choice and what we ultimately went with. This repo is now archived and is unlikely to be functional other than a point-in-time reference to an architecture I was exploring

A TaskIQ-based executor for Dagster using AWS SQS for distributed task execution.

## Overview

This project provides an alternative to dagster-celery using TaskIQ with AWS SQS. It demonstrates distributed job execution on AWS ECS with auto-scaling workers.

## Project Structure

```
dagster-taskiq/       # Core executor library (pip install dagster-taskiq)
dagster-taskiq-demo/  # Demo application with auto-scaling and load testing
deploy/               # Pulumi infrastructure code for AWS
```

## Quick Start

### Prerequisites

- `mise` (`brew install mise` and `mise install`)
- AWS CLI configured with credentials (`aws sts get-caller-identity`)
- Docker for building images

### Deploy to AWS

1. **Configure environment**:

   ```bash
   mise install
   mise run env-setup
   # Edit .env with your AWS settings
   ```

2. **Deploy infrastructure**:

   ```bash
   cd deploy
   uv run pulumi up --stack dev
   ```

3. **Build and push application**:

   ```bash
   ./scripts/build-and-push.sh
   cd deploy && uv run pulumi up --stack dev
   ```

4. **Access Dagster UI**:

   ```bash
   cd deploy && uv run pulumi stack output loadBalancerDns
   ```

## Development Tasks

Each subproject has its own mise tasks. From within a project directory:

```bash
mise run :install   # Install dependencies
mise run :test      # Run tests
mise run :lint      # Lint code (--fix to auto-fix)
mise run :format    # Format code (--check to check only)
mise run :checks    # Run all checks (lint + typecheck + test)
mise run :fixes     # Run all fixes (format and lint)
```

Run across all projects: `mise run //...:test`

## Observability

### Log Viewing

```bash
mise run logs:dagster-daemon
mise run logs:dagster-webserver
mise run logs:taskiq-worker
mise run logs:auto-scaler
```

### ECS Service Status

```bash
mise run aws:services
mise run ecs:status SERVICE_NAME=dagster-daemon
mise run aws:tasks
```

### Queue Monitoring

```bash
mise run queue:depth
mise run aws:queues
```

## Load Testing

From `dagster-taskiq-demo/`:

```bash
# Steady load
uv run python -m dagster_taskiq_demo.load_simulator.cli steady-load --jobs-per-minute 6 --duration 300

# Burst load
uv run python -m dagster_taskiq_demo.load_simulator.cli burst-load --burst-size 10 --burst-interval 5 --duration 600

# Mixed workload
uv run python -m dagster_taskiq_demo.load_simulator.cli mixed-workload --duration 600
```

## Manual Testing

See [TESTING.md](TESTING.md) for comprehensive testing procedures.

## Troubleshooting

- **Pulumi locks stuck**: `cd deploy && pulumi cancel`
- **Queue not processing**: Check worker status with `mise run ecs:status SERVICE_NAME=taskiq-worker`
- **Check logs**: `mise run logs:taskiq-worker`

## Documentation

- [dagster-taskiq/README.md](dagster-taskiq/README.md) - Executor library
- [dagster-taskiq-demo/README.md](dagster-taskiq-demo/README.md) - Demo application
- [deploy/README.md](deploy/README.md) - Infrastructure
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) - Development workflow
