# Manual Testing Guide

This guide provides step-by-step procedures for manually testing the Dagster TaskIQ executor implementation.

## Prerequisites Verification

Before starting tests, verify all prerequisites are met:

### 1. LocalStack Health Check

```bash
mise run localstack:status
```

Expected: JSON response with all services showing "available"

### 2. Infrastructure Deployment

```bash
cd deploy
mise run pulumi:up
```

Verify outputs include:
- ECS cluster created
- SQS queues created
- RDS database created
- CloudWatch log groups created

### 3. Docker Images Built and Pushed

```bash
./scripts/build-and-push.sh
cd deploy && mise run pulumi:up
```

Verify images are available:
```bash
mise run aws:images
```

### 4. ECS Services Running

```bash
# List all services
mise run aws:services

# Check specific service status
mise run ecs:status SERVICE_NAME=dagster-daemon
mise run ecs:status SERVICE_NAME=dagster-webserver
mise run ecs:status SERVICE_NAME=taskiq-worker
```

Expected: All services show `Status: ACTIVE` with `RunningCount >= DesiredCount`

## Basic Functionality Tests

### Test 1: Submit Simple Dagster Job

1. **Start Dagster locally** (if not running in ECS):
   ```bash
   cd dagster-taskiq-demo
   uv run python -m dagster dev
   ```

2. **Access Dagster UI**: http://localhost:3000

3. **Submit a test job**:
   - Navigate to Jobs in the UI
   - Select a simple job (e.g., `hello_world_job`)
   - Click "Launch Run"
   - Monitor the run status

4. **Verify task appears in SQS queue**:
   ```bash
   mise run queue:depth
   ```
   Expected: `ApproximateNumberOfMessages` increases briefly, then decreases as worker picks up task

5. **Verify worker picks up task**:
   ```bash
   mise run logs:taskiq-worker
   ```
   Look for log entries showing:
   - Task received from SQS
   - Step execution started
   - Step execution completed

6. **Verify job completes successfully**:
   - Check Dagster UI: Run status should show "Success"
   - Check logs for completion messages

### Test 2: Queue Depth Monitoring

Monitor queue during job execution:

```bash
# Watch queue depth in real-time
watch -n 1 'mise run queue:depth'
```

While a job runs, you should see:
- Messages appear when tasks are submitted
- Messages disappear as workers process them
- Queue depth returns to zero when job completes

### Test 3: Worker Health Verification

1. **Check worker service health**:
   ```bash
   mise run ecs:status SERVICE_NAME=taskiq-worker
   ```

2. **Check worker logs for errors**:
   ```bash
   mise run logs:taskiq-worker
   ```
   Look for:
   - Connection errors (should be none)
   - Task processing errors (should be none for successful jobs)
   - Health check messages

## Observability Verification

### Log Tailing

All services log to CloudWatch. Use these commands to tail logs:

```bash
# Dagster daemon logs
mise run logs:dagster-daemon

# Dagster webserver logs
mise run logs:dagster-webserver

# TaskIQ worker logs
mise run logs:taskiq-worker

# Auto-scaler logs
mise run logs:auto-scaler
```

### ECS Status Checks

Check service health and task counts:

```bash
# List all services
mise run aws:services

# Check specific service
mise run ecs:status SERVICE_NAME=dagster-daemon

# List running tasks
mise run aws:tasks
```

### Queue Monitoring

Monitor SQS queue attributes:

```bash
# Get queue depth
mise run queue:depth

# List all queues
mise run aws:queues
```

### CloudWatch Log Groups

All logs are stored in these CloudWatch log groups:
- `/aws/ecs/dagster-daemon-{environment}`
- `/aws/ecs/dagster-webserver-{environment}`
- `/aws/ecs/taskiq-worker-{environment}`
- `/aws/ecs/auto-scaler-{environment}`

Access via LocalStack UI: https://app.localstack.cloud

## Known Issues and Limitations

### 1. Queue Routing Tags Ignored (High Priority)

**Issue**: The `DAGSTER_TASKIQ_QUEUE_TAG` on steps/runs is currently not used when calling `task.kiq(...)`. All tasks go to the single broker queue regardless of tags.

**Location**: `dagster_taskiq/core_execution_loop.py:137`, `dagster_taskiq/executor.py:102`, `dagster_taskiq/launcher.py:200`

**Workaround**: Currently, all tasks use the default queue. Queue routing is planned for Phase 2 completion.

**Verification**:
- Set a queue tag on a step: `@op(tags={"dagster-taskiq/queue": "custom-queue"})`
- Submit job and check logs - task will still go to default queue
- Check SQS queue - all messages appear in the same queue

### 2. LocalStack SQS DelaySeconds Limitation (Medium Priority)

**Issue**: LocalStack's SQS implementation may not honor `DelaySeconds` reliably, causing integration tests to fail.

**Impact**: Priority-based delay mapping may not work correctly in LocalStack environment.

**Workaround**: Priority mapping is implemented correctly (`executor.py:318-337`), but delays may not be honored by LocalStack. This should work correctly in production AWS.

**Verification**:
- Submit jobs with different priorities
- Check delay labels in logs: `mise run logs:dagster-daemon`
- Note: Delays may not be visible in LocalStack

**Reference**: `dagster-taskiq/IMPLEMENTATION_PROGRESS.md` documents this limitation

### 3. Priority Inversion via SQS Delay (Fixed, Needs Verification)

**Status**: Fixed in implementation. Priority mapping now correctly maps higher Dagster priority to lower SQS delay.

**Implementation**: `executor.py:318-337` - `_priority_to_delay_seconds()` function

**Verification**:
- Submit jobs with different priority tags
- Check logs for: `priority=X, calculated_delay=Ys`
- Higher priority should result in lower delay (0s for default priority 5)

### 4. config_source Dropped (Medium Priority)

**Issue**: Executor/launcher accept `config_source` but `make_app()` ignores it and hard-codes SQS/S3 settings.

**Location**: `dagster_taskiq/make_app.py:37` ignores `config_source` parameter

**Workaround**: Use environment variables or direct configuration parameters instead of `config_source`.

**Verification**:
- Set `config_source` in executor config
- Check that custom settings are not applied
- Verify hard-coded defaults are used instead

### 5. Run Termination Unsupported (Medium Priority)

**Issue**: Launcher's `terminate()` method logs "not supported" and returns `False`.

**Location**: `dagster_taskiq/launcher.py:124`

**Status**: Cancellation support is in Phase 3 (not started). Draft implementation exists in `cancellable_broker.py` but not wired to executor.

**Workaround**: Use Dagster's built-in run cancellation, which may not propagate to TaskIQ workers.

**Verification**:
- Attempt to terminate a running job via Dagster UI
- Check logs - termination request may not reach workers
- Workers may continue processing until completion

### 6. Worker Health Check Regressed (Medium Priority)

**Issue**: Launcher advertises `supports_check_run_worker_health = True` but always returns `WorkerStatus.UNKNOWN`.

**Location**: `dagster_taskiq/launcher.py:248`, `launcher.py:328`

**Reason**: No result backend status is read to determine actual worker health.

**Workaround**: Check ECS service status directly:
```bash
mise run ecs:status SERVICE_NAME=taskiq-worker
```

**Verification**:
- Check worker health via Dagster API
- Should return `UNKNOWN` status
- Use ECS status checks instead for accurate health

## Load Testing Integration

### Running Load Scenarios

From `dagster-taskiq-demo/`:

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

### Monitoring During Load Tests

1. **Queue Depth**: Watch queue depth during load:
   ```bash
   watch -n 1 'mise run queue:depth'
   ```

2. **Worker Logs**: Monitor worker processing:
   ```bash
   mise run logs:taskiq-worker
   ```

3. **Auto-Scaling**: Check if workers scale up:
   ```bash
   mise run ecs:status SERVICE_NAME=taskiq-worker
   ```

4. **Dagster UI**: Monitor job runs in UI (http://localhost:3000)

### Verification After Load Tests

```bash
# Check exactly-once execution
cd dagster-taskiq-demo
uv run python -m dagster_taskiq_demo.load_simulator.cli verify --output verification_report.json

# Expected: 0 duplicate executions
```

## Troubleshooting Commands

### Service Not Starting

```bash
# Check service status
mise run ecs:status SERVICE_NAME=<service-name>

# Check service logs
mise run logs:<service-name>

# Check ECS task logs directly
TASK_ARN=$(mise run aws:tasks | jq -r '.taskArns[0]')
awslocal ecs describe-tasks --cluster <cluster> --tasks $TASK_ARN --region us-east-1
```

### Queue Not Processing

```bash
# Check queue depth
mise run queue:depth

# Check worker logs
mise run logs:taskiq-worker

# Check worker service status
mise run ecs:status SERVICE_NAME=taskiq-worker

# Check queue attributes
QUEUE_URL=$(cd deploy && uv run pulumi stack output queueUrl --stack local)
awslocal sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names All
```

### Database Connection Issues

```bash
# Check database endpoint
cd deploy
uv run pulumi stack output databaseEndpoint --stack local

# Check Dagster daemon logs for connection errors
mise run logs:dagster-daemon
```

### Image Not Found

```bash
# List available images
mise run aws:images

# Rebuild and push
./scripts/build-and-push.sh
cd deploy && mise run pulumi:up
```

## End-to-End Verification Checklist

- [ ] LocalStack running and healthy
- [ ] Infrastructure deployed (Pulumi stack up)
- [ ] Images built and pushed to ECR
- [ ] ECS services running (all show ACTIVE status)
- [ ] Simple job submitted and completes successfully
- [ ] Task appears in SQS queue (queue depth increases)
- [ ] Worker picks up task (logs show task processing)
- [ ] Job completes successfully (Dagster UI shows Success)
- [ ] Queue depth returns to zero
- [ ] Logs accessible via CloudWatch (all services)
- [ ] ECS status checks work correctly
- [ ] Load testing scenarios run successfully
- [ ] Exactly-once semantics verified (0 duplicates)
- [ ] Auto-scaling works during load (workers scale up/down)

## Next Steps

1. **Phase 2 Completion**: Complete queue routing tag support
2. **Phase 3**: Implement full cancellation support
3. **Health Check Enhancement**: Integrate result backend status for accurate health checks
4. **Config Source**: Wire `config_source` through to broker creation

Refer to `dagster-taskiq/IMPLEMENTATION_PROGRESS.md` for current status and roadmap.

