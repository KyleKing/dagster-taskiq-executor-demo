# Dagster TaskIQ Demo

Demo application showcasing Dagster with TaskIQ execution on AWS, featuring distributed job execution and auto-scaling.

## Features

- **Dagster Integration**: Complete orchestration platform with daemon and web UI
- **TaskIQ Execution**: Distributed task execution via AWS SQS using TaskIQ
- **Auto-Scaling**: SQS queue depth-based worker scaling on ECS
- **Load Simulator**: Testing framework for various scenarios (steady, burst, failure recovery)

## Quick Start

1. **Deploy infrastructure** (see [../deploy/README.md](../deploy/README.md)):

   ```bash
   cd deploy
   uv run pulumi up --stack dev
   ```

2. **Build and push images**:

   ```bash
   ./scripts/build-and-push.sh
   cd deploy && uv run pulumi up --stack dev
   ```

3. **Access Dagster UI**:

   ```bash
   cd deploy && uv run pulumi stack output dagsterWebserverUrl
   ```

## Load Testing

The load simulator provides various testing scenarios:

```bash
# Steady load: 6 jobs/minute for 5 minutes
uv run python -m dagster_taskiq_demo.load_simulator.cli steady-load --jobs-per-minute 6 --duration 300

# Burst load: 10 jobs every 5 minutes for 10 minutes
uv run python -m dagster_taskiq_demo.load_simulator.cli burst-load --burst-size 10 --burst-interval 5 --duration 600

# Mixed workload for 10 minutes
uv run python -m dagster_taskiq_demo.load_simulator.cli mixed-workload --duration 600

# Worker failure simulation
uv run python -m dagster_taskiq_demo.load_simulator.cli worker-failure --failure-burst-size 20 --recovery-interval 2 --duration 600
```

## Development

### Running Tests

```bash
mise run :test
```

### Code Style

```bash
mise run :lint --fix
mise run :format
mise run :checks  # All checks
```

## Monitoring

```bash
# From project root
mise run logs:dagster-daemon
mise run logs:taskiq-worker
mise run ecs:status SERVICE_NAME=taskiq-worker
mise run queue:depth
```

## Troubleshooting

- **Pulumi locks stuck**: `cd deploy && pulumi cancel`
- **Queue not processing**: Check worker status and logs

See [../TESTING.md](../TESTING.md) for comprehensive testing procedures.
