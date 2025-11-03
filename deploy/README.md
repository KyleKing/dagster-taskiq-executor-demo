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

```bash
cd deploy
pulumi cancel  # Release stuck locks
pulumi refresh # Sync state with cloud
```

## Additional Resources

- [Pulumi IDP Best Practices](https://www.pulumi.com/docs/idp/best-practices/)
- [Four Factors Framework](https://www.pulumi.com/docs/idp/best-practices/four-factors)
- [Pulumi Configuration](https://www.pulumi.com/docs/iac/concepts/config/)
