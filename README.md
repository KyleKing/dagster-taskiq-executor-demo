# Dagster TaskIQ Executor Demo

Based on dagster-celery, this project demonstrates a potentially new executor based on taskiq for better performance. Locally are projects demonstrating taskiq standalone with FastAPI and separately as an executor for Dagster. LocalStack and Pulumi are used to locally evaluate the new executor.

## Quick Start

### Prerequisites

- `mise` (`brew install mise` and `mise install`) - tool version management
- Docker Desktop (or compatible Docker engine)
- `awslocal` CLI (`uvx awscli-local` or `mise use pipx:awscli-local`)
- LocalStack Pro API key (`LOCALSTACK_AUTH_TOKEN`) for ECS, RDS, Cloud Map, ALB support

### Setup

1. **Configure environment**:

   ```bash
   mise install
   mr env-setup
   # Then edit .env with your LocalStack Pro token
   ```

1. **Start LocalStack**:

   ```bash
   mise run localstack:start
   ```

1. **Deploy infrastructure**:

   ```bash
   cd deploy && mise run pulumi:up
   ```

1. **Build and push application**:

   ```bash
   ./scripts/build-and-push.sh
   cd deploy && mise run pulumi:up
   ```

1. **Access UIs**:

   - LocalStack: https://app.localstack.cloud
   - Dagster: http://localhost:3000 (TODO: this is from ECS in LocalStack!)
   - (Optioanl) TaskIQ Dashboard: http://localhost:8080 (`./scripts/run-dashboard.sh`)

## Development Tasks

```bash
mise run install    # Install dependencies
mise run test       # Run tests
mise run lint       # Lint code (pass --fix to auto-fix)
mise run format     # Format code (pass --check to check only)
mise run checks     # Run all checks (lint + typecheck + test)
mise run fixes      # Run all fixes (format and lint fixes)
```

Pass custom arguments: `mise run test -- -v -k "test_name"`

Run multiple tasks in parallel: `mise run format ::: lint ::: typecheck`

## Load Testing

Run various scenarios to test system behavior from `./dagster-taskiq-demo/`

```bash
# Steady load: 6 jobs/minute for 5 minutes
uv run python -m dagster_taskiq_demo.load_simulator.cli steady-load --jobs-per-minute 6 --duration 300

# Burst load: 10 jobs every 5 minutes for 10 minutes
uv run python -m dagster_taskiq_demo.load_simulator.cli burst-load --burst-size 10 --burst-interval 5 --duration 600

# Mixed workload for 10 minutes
uv run python -m dagster_taskiq_demo.load_simulator.cli mixed-workload --duration 600

# Worker failure simulation
uv run python -m dagster_taskiq_demo.load_simulator.cli worker-failure --failure-burst-size 20 --recovery-interval 2 --duration 600

# Network partition simulation
uv run python -m dagster_taskiq_demo.load_simulator.cli network-partition --max-burst-size 5 --duration 600
```

## Development Workflow

**Application changes**:

```bash
./scripts/build-and-push.sh  # Rebuild and push image
# ECS services automatically pick up new image
```

**Infrastructure changes**:

```bash
cd deploy && mise run pulumi:up
```

## Troubleshooting

**Common Issues**:

- **Pulumi locks stuck**: `cd deploy && pulumi cancel`
- **LocalStack not responding**: `mise run localstack:restart`
- **Queue not processing**: Verify SQS configuration and worker health

**Cleanup**:

```bash
cd deploy && pulumi destroy
mise run localstack:stop
```
