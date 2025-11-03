# Dagster TaskIQ Executor Demo

Production-like AWS deployment of Dagster with TaskIQ execution running locally using LocalStack. Demonstrates distributed job execution, auto-scaling, failure recovery, and exactly-once execution semantics.

## Architecture

- **Dagster**: Orchestration platform with daemon and web UI
- **TaskIQ**: Custom async worker implementation for distributed task execution
- **LocalStack**: Local AWS service emulation (SQS, ECS, RDS)
- **Load Simulator**: Testing framework for various load scenarios

## Quick Start

### Prerequisites
- `mise` (`brew install mise` and `mise install`) - tool version management
- Docker Desktop (or compatible Docker engine)
- `awslocal` CLI (`uvx awscli-local` or `mise use pipx:awscli-local`)
- LocalStack Pro API key (`LOCALSTACK_AUTH_TOKEN`) for ECS, RDS, Cloud Map, ALB

### Setup

1. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your LocalStack Pro token
   ```

2. **Start LocalStack**:
   ```bash
   mise run localstack:start
   ```

3. **Deploy infrastructure**:
   ```bash
   cd deploy && mise run pulumi:up
   ```

4. **Build and push application**:
   ```bash
   ./scripts/build-and-push.sh
   ```

5. **Start Dagster services**:
   ```bash
   cd dagster-taskiq-demo && python -m dagster dev
   ```

6. **Access UIs**:
   - Dagster: http://localhost:3000
   - LocalStack: https://app.localstack.cloud

## Development Tasks

```bash
mise run install    # Install dependencies
mise run test       # Run tests
mise run lint       # Lint code (pass --fix to auto-fix)
mise run format     # Format code (pass --check to check only)
mise run typecheck  # Run type checkers
mise run checks     # Run all checks (lint + typecheck + test)
```

Pass custom arguments: `mise run test -- -v -k "test_name"`

Run multiple tasks in parallel: `mise run format ::: lint ::: typecheck`

## Load Testing

Run various scenarios to test system behavior:

```bash
# Steady load: 6 jobs/minute for 5 minutes
python -m dagster_taskiq_demo.load_simulator.cli steady-load --jobs-per-minute 6 --duration 300

# Burst load: 10 jobs every 5 minutes for 10 minutes
python -m dagster_taskiq_demo.load_simulator.cli burst-load --burst-size 10 --burst-interval 5 --duration 600

# Mixed workload for 10 minutes
python -m dagster_taskiq_demo.load_simulator.cli mixed-workload --duration 600

# Worker failure simulation
python -m dagster_taskiq_demo.load_simulator.cli worker-failure --failure-burst-size 20 --recovery-interval 2 --duration 600

# Network partition simulation
python -m dagster_taskiq_demo.load_simulator.cli network-partition --max-burst-size 5 --duration 600
```

### Verification

Check exactly-once execution:
```bash
python -m dagster_taskiq_demo.load_simulator.cli verify --output verification_report.json
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

**Configuration updates**:
```bash
cd deploy && mise run config set queueName my-queue
mise run pulumi:up
```

## Configuration

Environment variables:
- `AWS_DEFAULT_REGION` (default `us-east-1`) - AWS region for LocalStack
- `LOCALSTACK_SQS_QUEUE_NAME` - Override queue name
- `LOCALSTACK_ECS_CLUSTER_NAME` - Override cluster name
- `LOCALSTACK_PERSISTENCE=0` - Disable persistent state

## Implementation Notes

### Custom Worker Implementation

Uses custom async worker (not TaskIQ framework) for better Dagster integration:
- **Dagster Integration**: Aligns with Dagster's op/step execution lifecycle
- **Exactly-Once**: PostgreSQL idempotency storage prevents duplicate execution
- **Custom Payloads**: Structured `OpExecutionTask` with run/step metadata
- **Result Reporting**: Polling via idempotency storage for better integration
- **Async Control**: Fine-grained execution, shutdown, and health check control

### Error Handling

- **Worker Crashes**: SQS visibility timeout triggers redelivery; idempotency check prevents duplicates
- **SQS Failures**: Exponential backoff with jitter; circuit breaker after 5 failures
- **Dagster Daemon**: ECS health checks and automatic restart; PostgreSQL persistence
- **Network Partitions**: Local execution context caching; reconciliation on restoration

## Troubleshooting

**Common Issues**:
- **Pulumi locks stuck**: `cd deploy && pulumi cancel`
- **LocalStack not responding**: `mise run localstack:restart`
- **Dagster connection issues**: Check webserver port (default 3000)
- **Queue not processing**: Verify SQS configuration and worker health

**Cleanup**:
```bash
cd deploy && pulumi destroy
mise run localstack:stop
```

## Technology Stack

- **Docker Bake**: Declarative, reproducible container builds (`docker-bake.hcl`)
- **Image Build Separation**: Separate build/push from Pulumi using `awslocal` CLI
- **Local Pulumi**: Runs locally, no Docker container needed
- **ECS Support**: Requires Docker socket mount in LocalStack container
- **LocalStack Pro**: Required for ECS, RDS, Service Discovery, ALB APIs
