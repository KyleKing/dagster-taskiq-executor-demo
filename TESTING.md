# Manual Testing Guide

Step-by-step procedures for manually testing the Dagster TaskIQ executor.

## Prerequisites Verification

### 1. AWS Configuration

```bash
aws sts get-caller-identity
```

Expected: JSON response with account ID and ARN

### 2. Infrastructure Deployment

```bash
cd deploy
uv run pulumi up --stack dev
```

### 3. Docker Images Built and Pushed

```bash
./scripts/build-and-push.sh
cd deploy && uv run pulumi up --stack dev
```

Verify images:

```bash
mise run aws:images
```

### 4. ECS Services Running

```bash
mise run aws:services
mise run ecs:status SERVICE_NAME=dagster-daemon
mise run ecs:status SERVICE_NAME=dagster-webserver
mise run ecs:status SERVICE_NAME=taskiq-worker
```

Expected: All services show `Status: ACTIVE` with `RunningCount >= DesiredCount`

## Basic Functionality Tests

### Test 1: Submit Simple Dagster Job

1. **Get Dagster UI URL**:

   ```bash
   cd deploy && uv run pulumi stack output dagsterWebserverUrl
   ```

2. **Submit a test job**:

   - Navigate to Jobs in the UI
   - Select a simple job
   - Click "Launch Run"
   - Monitor the run status

3. **Verify task appears in SQS queue**:

   ```bash
   mise run queue:depth
   ```

4. **Verify worker picks up task**:

   ```bash
   mise run logs:taskiq-worker
   ```

5. **Verify job completes successfully** in Dagster UI

### Test 2: Queue Depth Monitoring

```bash
watch -n 1 'mise run queue:depth'
```

### Test 3: Worker Health Verification

```bash
mise run ecs:status SERVICE_NAME=taskiq-worker
mise run logs:taskiq-worker
```

## Observability

### Log Tailing

```bash
mise run logs:dagster-daemon
mise run logs:dagster-webserver
mise run logs:taskiq-worker
mise run logs:auto-scaler
```

### ECS Status

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
```

### Monitoring During Load Tests

1. Queue depth: `watch -n 1 'mise run queue:depth'`
2. Worker logs: `mise run logs:taskiq-worker`
3. Auto-scaling: `mise run ecs:status SERVICE_NAME=taskiq-worker`

## Known Limitations

- **Run termination**: Not supported
- **Worker health checks**: Not supported (returns UNKNOWN)
- **Queue routing tags**: Not supported (all tasks go to single queue)

## Troubleshooting

### Service Not Starting

```bash
mise run ecs:status SERVICE_NAME=<service-name>
mise run logs:<service-name>
```

### Queue Not Processing

```bash
mise run queue:depth
mise run logs:taskiq-worker
mise run ecs:status SERVICE_NAME=taskiq-worker
```

## End-to-End Verification Checklist

- [ ] AWS credentials configured
- [ ] Infrastructure deployed
- [ ] Images built and pushed to ECR
- [ ] ECS services running
- [ ] Simple job submitted and completes
- [ ] Task appears in SQS queue
- [ ] Worker picks up task
- [ ] Job completes successfully
- [ ] Logs accessible via CloudWatch
