# Dagster TaskIQ Demo

Demo application showcasing Dagster with TaskIQ execution on LocalStack, featuring distributed job execution, auto-scaling, and exactly-once semantics.

## Features

- **Dagster Integration**: Complete orchestration platform with daemon and web UI
- **TaskIQ Execution**: Custom async worker implementation (not TaskIQ framework) for better Dagster integration
- **Exactly-Once Semantics**: PostgreSQL idempotency storage prevents duplicate execution
- **Auto-Scaling**: SQS queue depth-based worker scaling on ECS
- **Load Simulator**: Testing framework for various scenarios (steady, burst, failure recovery)
- **LocalStack**: Local AWS service emulation (SQS, ECS, RDS)

## Architecture

### Custom Worker Implementation

While using TaskIQ terminology, this project implements a custom async worker using aioboto3 for SQS message consumption instead of the TaskIQ framework. Reasons:

1. **Dagster Integration**: TaskIQ's task model doesn't align with Dagster's op/step execution lifecycle
2. **Idempotency Requirements**: Custom exactly-once execution with PostgreSQL storage
3. **Payload Handling**: Structured `OpExecutionTask` payloads with run/step metadata
4. **Result Reporting**: Polling via idempotency storage for better Dagster integration
5. **Async Control**: Fine-grained control over execution, shutdown, and health checks

## Quick Start

1. **Set up environment**:
   ```bash
   cp .env.example .env.test
   # Edit .env.test with your configuration
   ```

2. **Start services**:
   ```bash
   # From project root
   mise run localstack:start
   cd deploy && mise run pulumi:up
   cd ../..
   ./scripts/build-and-push.sh
   ```

3. **Run Dagster**:
   ```bash
   cd dagster-taskiq-demo
   python -m dagster dev
   ```

4. **Access UI**: Open http://localhost:3000 for Dagster webserver

## Load Testing

The load simulator provides various testing scenarios:

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
# Export verification report
python -m dagster_taskiq_demo.load_simulator.cli verify --output verification_report.json

# Or export as CSV
python -m dagster_taskiq_demo.load_simulator.cli verify --output verification_report.csv --format csv
```

## Development

### Code Style

- Python 3.13 with functional patterns (DRY, YAGNI)
- SQLAlchemy v2 style: import from `sqlalchemy`, use `text()` for SQL strings
- Handle Result objects appropriately (`.scalar()`, `.scalars()`, `.mappings()`)
- Single quotes, no semicolons

### Testing

```bash
# Run all tests
mise run test

# Run with specific pattern
mise run test -- -v -k "test_name"

# Lint and format
mise run lint --fix
mise run format
```

### Application Changes

1. Modify code in `src/dagster_taskiq_demo/`
2. Rebuild and push image: `./scripts/build-and-push.sh`
3. Restart Dagster services

## Error Handling

**Failure Scenarios and Recovery**:

1. **Worker Crashes**: SQS visibility timeout triggers redelivery; new worker checks idempotency record
2. **SQS Connection Failures**: Exponential backoff with jitter (1s, 2s, 4s, 8s, 16s); circuit breaker after 5 failures
3. **Dagster Daemon Failures**: ECS health checks and automatic restart; persistent PostgreSQL storage
4. **Network Partitions**: Workers cache execution context locally; reconciliation on restoration

## Monitoring

- **Dagster UI**: http://localhost:3000 - Job runs, execution logs, system health
- **LocalStack UI**: http://localhost:4566/_localstack/health - AWS service metrics
- **Structured Logs**: Comprehensive logging across all components
- **Auto-Scaling**: Monitor ECS service desired count during load scenarios

## Configuration

Key configuration files:
- `src/dagster_taskiq_demo/config/` - Application settings
- `dagster.yaml` - Dagster configuration
- `.env.test` - Test environment variables

## Troubleshooting

**Common Issues**:
- **Pulumi locks stuck**: `cd deploy && pulumi cancel`
- **LocalStack not responding**: `mise run localstack:restart`
- **Dagster connection issues**: Check webserver port (default 3000)
- **Queue not processing**: Verify SQS configuration and worker health

**Verification Procedures**:
- **Exactly-Once**: Check for duplicate executions (should be 0)
- **Auto-Scaling**: Monitor ECS desired count during load changes
- **Failure Recovery**: Verify jobs retry on different workers
- **Performance**: Monitor execution times and queue depth