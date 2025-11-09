# Cancellation Guide

This guide covers how to configure and use task cancellation in dagster-taskiq.

## Overview

Task cancellation allows you to terminate running Dagster tasks via the Dagster UI or API. When enabled, the system uses a separate SQS queue for cancellation messages, and workers automatically listen for and process cancellation requests.

## Architecture

### Components

1. **CancellableSQSBroker** (`src/dagster_taskiq/cancellable_broker.py`)
   - Extends the base SQS broker with cancellation support
   - Manages a separate cancellation queue
   - Sends cancellation messages when `cancel_task()` is called
1. **CancellableReceiver** (`src/dagster_taskiq/cancellable_receiver.py`)
   - Worker-side receiver that polls both the main task queue and cancellation queue
   - Matches cancellation messages to running tasks by task ID
   - Cancels asyncio tasks when cancellation is requested
1. **Launcher Integration** (`src/dagster_taskiq/launcher.py`)
   - `terminate()` method sends cancellation requests
   - Stores task IDs in run tags for tracking
1. **Core Execution Loop** (`src/dagster_taskiq/core_execution_loop.py`)
   - Requests cancellation on shutdown/interrupt
   - Handles graceful cleanup of cancelled tasks

### Queue Naming Convention

The cancellation queue is automatically created with the naming convention:

```
{main-queue-name}-cancels
```

For example:

- Main queue: `dagster-tasks` → Cancel queue: `dagster-tasks-cancels`
- Main queue: `dagster-tasks.fifo` → Cancel queue: `dagster-tasks-cancels.fifo`

**Note**: The cancel queue must be created manually in AWS SQS (or via infrastructure as code). The worker entrypoint (`tests/worker_entrypoint.py`) shows an example of creating both queues.

## Configuration

### Enabling Cancellation

Cancellation can be enabled via environment variable or configuration:

#### Environment Variable

```bash
export DAGSTER_TASKIQ_ENABLE_CANCELLATION=1
```

#### Executor Configuration

```yaml
execution:
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
    config_source:
      enable_cancellation: true
```

#### Launcher Configuration

```yaml
run_launcher:
  module: dagster_taskiq.launcher
  class: TaskiqRunLauncher
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks'
    config_source:
      enable_cancellation: true
```

### Worker Configuration

Workers automatically use `CancellableReceiver` when cancellation is enabled. The CLI (`dagster_taskiq.cli`) automatically sets up the receiver:

```bash
dagster-taskiq worker start --config config.yaml
```

The receiver is configured automatically when `enable_cancellation` is set in the config or environment.

## Usage

### Terminating a Run

#### Via Dagster UI

1. Navigate to the run in the Dagster UI
1. Click the "Terminate" button
1. The launcher will send a cancellation message to the cancel queue
1. The worker will receive the cancellation and cancel the running task

#### Via Python API

```python
from dagster import DagsterInstance

instance = DagsterInstance.get()
launcher = instance.run_launcher

# Terminate a running run
success = launcher.terminate(run_id="your-run-id")
if success:
    print("Cancellation requested")
else:
    print("Failed to request cancellation")
```

### How It Works

1. **Cancellation Request**: When `terminate()` is called, the launcher:

   - Retrieves the task ID from run tags
   - Calls `broker.cancel_task(task_id)` on the `CancellableSQSBroker`
   - Sends a cancellation message to the cancel queue

1. **Worker Processing**: The `CancellableReceiver`:

   - Polls the cancel queue alongside the main task queue
   - Parses cancellation messages to extract task IDs
   - Matches task IDs to running asyncio tasks
   - Cancels matching tasks using `task.cancel()`

1. **Task Cleanup**: When a task is cancelled:

   - The asyncio task is cancelled, raising `CancelledError`
   - The task execution stops gracefully
   - Any cleanup code in `finally` blocks runs
   - The result backend may or may not contain a result (depending on timing)

## Troubleshooting

### Cancellation Not Working

**Symptoms**: Tasks continue running after calling `terminate()`

**Possible Causes**:

1. **Cancellation not enabled**

   - Check that `enable_cancellation` is set to `true` in config
   - Verify `DAGSTER_TASKIQ_ENABLE_CANCELLATION=1` environment variable

1. **Cancel queue not created**

   - Ensure the cancel queue exists: `{main-queue-name}-cancels`
   - Check queue permissions allow send/receive

1. **Worker not using CancellableReceiver**

   - Verify worker was started with cancellation enabled
   - Check worker logs for receiver initialization

1. **Task ID mismatch**

   - Ensure task IDs are stored in run tags
   - Verify task ID format matches between launcher and receiver

### Debugging Steps

1. **Check Launcher Logs**

   ```python
   # Look for cancellation request messages
   instance.all_logs(run_id)
   # Should contain: "Requested Taskiq task cancellation."
   ```

1. **Check Worker Logs**

   ```bash
   # Look for cancellation messages
   dagster-taskiq worker start --log-level DEBUG
   # Should show: "Cancelling task {task_id}"
   ```

1. **Verify Queue Messages**

   ```python
   import boto3
   sqs = boto3.client('sqs')
   response = sqs.receive_message(
       QueueUrl='https://sqs.../dagster-tasks-cancels',
       MaxNumberOfMessages=10
   )
   # Check if cancellation messages are in the queue
   ```

1. **Check Task ID Storage**

   ```python
   run = instance.get_run_by_id(run_id)
   task_id = run.tags.get('dagster-taskiq/task_id')
   print(f"Task ID: {task_id}")
   ```

### Common Issues

#### Task ID Not Found

**Error**: "Taskiq task ID missing; unable to cancel run task."

**Solution**: Ensure the run was launched via `TaskiqRunLauncher`. The task ID is stored when the task is submitted.

#### Cancel Queue Not Found

**Error**: Queue does not exist errors when sending cancellation

**Solution**: Create the cancel queue manually or via infrastructure:

```bash
aws sqs create-queue --queue-name dagster-tasks-cancels
```

#### Worker Not Receiving Cancellations

**Symptoms**: Cancellation messages sent but tasks not cancelled

**Possible Causes**:

- Worker not using `CancellableReceiver`
- Task ID format mismatch
- Worker polling interval too long

**Solution**:

- Verify receiver is configured: check worker startup logs
- Ensure task IDs match exactly (string format)
- Reduce `wait_time_seconds` for faster polling

## Best Practices

1. **Always Create Cancel Queue**: Ensure the cancel queue exists before starting workers
1. **Monitor Queue Depth**: Watch for stuck cancellation messages
1. **Use FIFO Queues**: For better ordering guarantees, use FIFO queues for both main and cancel queues
1. **Test Cancellation**: Verify cancellation works in your environment before relying on it
1. **Handle Cancellation Gracefully**: Ensure your tasks handle `CancelledError` appropriately

## Limitations

1. **Cooperative Cancellation**: Tasks must check for cancellation periodically; long-running operations may not cancel immediately
1. **Result Availability**: Cancelled tasks may or may not have results in the result backend
1. **Idempotency**: Ensure your tasks are idempotent, as cancellation doesn't guarantee the task won't be retried
1. **Queue Ordering**: Standard queues don't guarantee order; FIFO queues provide better ordering

## Examples

### Full Configuration Example

```yaml
# dagster.yaml
run_launcher:
  module: dagster_taskiq.launcher
  class: TaskiqRunLauncher
  config:
    queue_url: 'https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks.fifo'
    region_name: 'us-east-1'
    config_source:
      enable_cancellation: true
      is_fair_queue: true  # Auto-detected from .fifo suffix
      wait_time_seconds: 20
      max_number_of_messages: 1
```

### Programmatic Cancellation

```python
from dagster import DagsterInstance

instance = DagsterInstance.get()

# Get all running runs
runs = instance.get_runs(
    filters=RunsFilter(statuses=[DagsterRunStatus.STARTED])
)

# Cancel all running runs
launcher = instance.run_launcher
for run in runs:
    if launcher.terminate(run.run_id):
        print(f"Cancelled run {run.run_id}")
    else:
        print(f"Failed to cancel run {run.run_id}")
```

## See Also

- `IMPLEMENTATION_PROGRESS.md` - Implementation details
- `README.md` - General usage and configuration
- `TESTING.md` - Testing procedures
