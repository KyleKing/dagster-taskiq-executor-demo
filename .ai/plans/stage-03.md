# Stage 03 – Auto-Scaler & Failure Simulation

## Goals
- Deliver the auto-scaling control loop that adjusts TaskIQ worker capacity based on queue depth and simulates failure scenarios.
- Integrate the service into the infrastructure stack so it runs continuously in LocalStack ECS.

## Current State
- `app/src/dagster_taskiq/auto_scaler/__init__.py` is empty; no monitoring or scaling logic exists.
- Requirements specify scale-up/down thresholds, cooldowns, and failure simulation tactics.
- Pulumi stack does not yet deploy an auto-scaler task/service.

## Tasks
1. **Implement queue metric ingestion**
   - Use `boto3.client("sqs").get_queue_attributes()` to pull `ApproximateNumberOfMessages`, `ApproximateNumberOfMessagesNotVisible`, and `ApproximateAgeOfOldestMessage`.
   - Collect metrics at a configurable interval (`settings.autoscaler_cooldown_seconds`).
   - Surface structured logs and optional Prometheus-style metrics for future scraping.

2. **Scaling decision engine**
   - Encode logic from the design doc:  
     - Scale up when `visible_messages > current_workers * autoscaler_scale_up_threshold`.  
     - Scale down when `visible_messages < current_workers * autoscaler_scale_down_threshold`.  
     - Clamp between `autoscaler_min_workers` and `autoscaler_max_workers`.  
   - Track last scale action timestamp to enforce cooldowns and avoid thrashing.
   - When scaling, call `boto3.client("ecs").update_service()` targeting the worker service created in Stage 02.

3. **Failure simulation hooks**
   - Implement routines to:  
     a. Randomly stop a worker task (`ecs.stop_task`) to mimic instance termination.  
     b. Drain tasks by reducing desired count to zero, waiting for steady state, then scaling back.  
     c. Simulate network partitions by toggling queue access (e.g., temporarily attach a restrictive security group or disable message processing via configuration flag).  
   - Make these behaviours configurable (intervals, enable/disable flags) via settings.

4. **Service packaging**
   - Provide a CLI/entrypoint (`python -m dagster_taskiq.auto_scaler.service`) that runs the control loop asynchronously.
   - Add health checks (e.g., HTTP `/healthz`) so ECS can determine liveness.
   - Update Pulumi to build an ECS task definition & service for the auto-scaler, injecting IAM permissions for `sqs`, `ecs`, and `cloudwatch`.

5. **Monitoring & alerts groundwork**
   - Emit metrics/logs that can feed into CloudWatch dashboards (even if LocalStack stubs them).  
   - Prepare placeholder alerting configuration (e.g., log messages when queue age exceeds threshold) to meet reliability requirements.

6. **Testing**
   - Unit test scaling decisions with parametrised scenarios covering thresholds, cooldowns, clamping, and failure simulation toggles.
   - Mock `boto3` clients using `botocore.stub.Stubber` to verify API payloads.
   - Ensure tests run quickly and deterministically (no real sleeps—patch with fast loops).

## Exit Criteria
- Auto-scaler module monitors queue depth, updates ECS service counts, and can trigger failure simulations on demand.
- Pulumi stack provisions and wires the auto-scaler service with necessary IAM permissions.
- Tests verifying scaling decisions and API payloads pass locally.
- Operational docs explain how to enable/disable failure simulation during demos.
