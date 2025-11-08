# Pulumi Infrastructure Deployment

Infrastructure as code for deploying the Dagster TaskIQ LocalStack demo using Pulumi best practices with Pulumi.yaml configuration.

## Architecture

Follows the [Four Factors Framework](https://www.pulumi.com/docs/idp/best-practices/four-factors):

- **Templates**: Reusable code patterns in `components/` and `modules/`
- **Components**: Encapsulated AWS resources (ECS clusters, RDS instances)
- **Environments**: Configuration via `Pulumi.<stack>.yaml` files
- **Policies**: Governance through code structure and validation

## Directory Structure

**`components/`** - Generic, reusable AWS primitives:

- Technology-focused thin wrappers (VPC, ECS, RDS, SQS)
- Functions returning dataclasses, independently importable
- Examples: `sqs_fifo.py`, `ecs_helpers.py`, `rds_postgres.py`

**`modules/`** - Application-specific infrastructure bundles:

- Compose multiple components with application logic
- Include Dagster, TaskIQ, and app-specific concerns
- Examples: `dagster.py` (complete deployment), `taskiq.py` (queues + workers + IAM)

**Guideline**: Reusable across projects → `components/`. Application-specific → `modules/`.

## Quick Start

1. **Prerequisites**: Pulumi CLI, Python dependencies via `uv`
1. **Start LocalStack**: `docker compose up -d localstack`
1. **Deploy infrastructure**: `mise run up`
1. **Build and push images**: `./scripts/build-and-push.sh`

## Configuration

Uses `StackSettings` in `config.py` for structured configuration:

- Override per-environment values in `Pulumi.<stack>.yaml`
- Avoid hard-coding values; use configuration for environment-specific settings
- All configuration managed through Pulumi.yaml (not ESC)

## TaskIQ Demo Module

Optional module disabled by default. Enable with:

```bash
cd deploy
uv run pulumi config set --path taskiqDemo.enabled true --stack local
uv run pulumi config set --path taskiqDemo.queueName taskiq-demo --stack local
uv run pulumi config set --path taskiqDemo.imageTag taskiq-demo --stack local
uv run pulumi config set --path taskiqDemo.apiDesiredCount 1 --stack local
uv run pulumi config set --path taskiqDemo.workerDesiredCount 1 --stack local
cd ..
```

Deploy with:

```bash
mise run push:taskiq-demo
mise run demo:taskiq
```

Exports additional outputs when enabled: `taskiqDemoQueueUrl`, `taskiqDemoApiServiceName`, `taskiqDemoWorkerServiceName`, `taskiqDemoSecurityGroupId`.

## Commands

```bash
mise run up         # Deploy infrastructure
mise run preview    # Preview changes
mise run destroy    # Destroy infrastructure
mise run refresh    # Refresh state from cloud
mise run demo:taskiq # Build/push TaskIQ demo and deploy (requires taskiqDemo.enabled=true)
```

## Best Practices

- **Composable Environments**: Stack configurations build upon shared base settings
- **Component Composition**: Infrastructure modules compose primitive components
- **Policies as Tests**: Validation logic ensures compliance
- **Cost Control**: Constrained inputs prevent resource over-provisioning
- **Security Updates**: Centralized component updates for security patches

## Development

**Infrastructure changes**:

```bash
cd deploy
# Edit infrastructure code
mise run up
```

**Configuration updates**:

```bash
cd deploy
uv run pulumi config set queueName my-new-queue --stack local
mise run up
```

**Troubleshooting**:

See [Troubleshooting & Recovery](#troubleshooting--recovery) section below for detailed guidance.

## Observability

### Log Viewing Commands

From project root, use mise tasks to tail CloudWatch logs:

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

### ECS Service Status

```bash
# List all services
mise run aws:services

# Check specific service
mise run ecs:status SERVICE_NAME=dagster-daemon
mise run ecs:status SERVICE_NAME=taskiq-worker

# List running tasks
mise run aws:tasks
```

### Queue Monitoring

```bash
# Check queue depth
mise run queue:depth

# Get queue URL from stack
uv run pulumi stack output queueUrl --stack local
```

### Stack Outputs

Get infrastructure URLs and identifiers:

```bash
# Queue URL
uv run pulumi stack output queueUrl --stack local

# Database endpoint
uv run pulumi stack output databaseEndpoint --stack local

# ECS cluster name
uv run pulumi stack output clusterName --stack local

# All outputs
uv run pulumi stack output --stack local
```

## Troubleshooting & Recovery

### Common Issues

#### Duplicate Resource URN Errors

**Symptom**: `error: Duplicate resource URN 'urn:pulumi:local::localstack-ecs-sqs::aws:ecs/service:Service::taskiq-demo-worker-service'`

**Cause**: Multiple resources with the same logical name in Pulumi code.

**Solution**:
1. Check for duplicate resource definitions in `__main__.py` and modules
2. Ensure each resource has a unique logical name
3. Use `pulumi:validate` to detect issues before deploying
4. If state is corrupted, use `pulumi:reset:hard` to start fresh

#### State Drift (Pulumi state out of sync with LocalStack)

**Symptom**: `pulumi up` fails with resource not found or already exists errors.

**Solution**:
1. **Refresh state**: `mise run pulumi:refresh` (syncs Pulumi state with actual infrastructure)
2. **Repair state**: `mise run pulumi:state:repair` (attempts automatic state repair)
3. **Validate**: `mise run pulumi:validate` (preview changes without applying)

#### LocalStack State Corruption

**Symptom**: LocalStack errors or unexpected behavior after failures.

**Solution**: Use reset strategies below.

### Reset Strategies

#### Soft Reset (Recommended for most cases)

Gracefully destroys resources, cleans LocalStack, and refreshes state:

```bash
cd deploy
mise run pulumi:reset:soft
```

**What it does**:
1. Destroys all Pulumi-managed resources
2. Stops LocalStack
3. Cleans LocalStack volume data
4. Restarts LocalStack
5. Initializes stack if needed
6. Refreshes state

**Use when**: You want to clean up while preserving stack configuration.

#### Hard Reset (Nuclear option for major failures)

Completely removes Pulumi stack and LocalStack state:

```bash
cd deploy
mise run pulumi:reset:hard
```

**What it does**:
1. Stops LocalStack
2. Deletes all LocalStack data
3. **Deletes Pulumi stack** (removes state file)
4. Restarts LocalStack
5. Initializes fresh stack

**Use when**:
- State is severely corrupted
- Duplicate URN errors persist
- You need a completely clean slate
- After hard reset, you'll need to run `pulumi:up` to recreate everything

#### Quick Reset (Original behavior)

Alias for soft reset - maintains backward compatibility:

```bash
cd deploy
mise run pulumi:reset
```

### State Management Commands

```bash
cd deploy

# List all resources in state
mise run pulumi:state:list

# Validate state without applying changes
mise run pulumi:validate

# Refresh state to sync with LocalStack
mise run pulumi:refresh

# Repair corrupted state
mise run pulumi:state:repair

# Delete stack (doesn't destroy resources)
mise run pulumi:state:delete

# Initialize stack if missing
mise run pulumi:state:init
```

### Recovery Workflow

**For minor issues**:
1. `mise run pulumi:validate` - Check what's wrong
2. `mise run pulumi:refresh` - Sync state
3. `mise run pulumi:up` - Try deploying again

**For state corruption**:
1. `mise run pulumi:state:repair` - Attempt repair
2. If that fails: `mise run pulumi:reset:soft` - Soft reset
3. If still failing: `mise run pulumi:reset:hard` - Hard reset, then `pulumi:up`

**For duplicate URN errors**:
1. Fix the code (remove duplicate resource definitions)
2. `mise run pulumi:reset:hard` - Clean slate
3. `mise run pulumi:up` - Fresh deployment

### Best Practices for Reliability

1. **Always preview before deploying**: `mise run pulumi:validate`
2. **Use soft reset for routine cleanup**: Preserves stack config
3. **Save stack config**: `Pulumi.local.yaml` is version-controlled
4. **Monitor state drift**: Run `pulumi:refresh` periodically during development
5. **Don't modify resources outside Pulumi**: Always use Pulumi for changes

### Making Pulumi More Reliable

1. **Unique Resource Names**: Ensure all resources have unique logical names
2. **Idempotent Operations**: Design infrastructure code to be safely re-runnable
3. **State Validation**: Use `pulumi:validate` before every deployment
4. **Incremental Changes**: Make small, incremental changes rather than large refactors
5. **Component Encapsulation**: Use components/modules to group related resources
6. **Error Handling**: Handle Pulumi errors gracefully in infrastructure code

## Additional Resources

- [Pulumi IDP Best Practices](https://www.pulumi.com/docs/idp/best-practices/)
- [Four Factors Framework](https://www.pulumi.com/docs/idp/best-practices/four-factors)
- [Pulumi Configuration](https://www.pulumi.com/docs/iac/concepts/config/)
- [Pulumi State Management](https://www.pulumi.com/docs/iac/concepts/state/)
