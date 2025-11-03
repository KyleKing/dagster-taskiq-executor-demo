# Pulumi Infrastructure Deployment

This directory contains Pulumi infrastructure as code for deploying the Dagster TaskIQ LocalStack demo. It follows Pulumi best practices using Pulumi.yaml for configuration instead of ESC.

## Best Practices

### Core Concepts

The deployment follows the [Four Factors Framework](https://www.pulumi.com/docs/idp/best-practices/four-factors): Templates, Components, Environments, and Policies.

- **Templates**: Reusable code patterns in `components/` and `modules/`
- **Components**: Encapsulated AWS resources (e.g., ECS clusters, RDS instances)
- **Environments**: Configuration managed via `Pulumi.<stack>.yaml` files
- **Policies**: Governance through code structure and validation

### Key Patterns

- **[Composable Environments](https://www.pulumi.com/docs/idp/best-practices/patterns/composable-environments)**: Stack configurations build upon shared base settings
- **[Components Using Other Components](https://www.pulumi.com/docs/idp/best-practices/patterns/components-using-other-components)**: Infrastructure modules compose primitive components
- **[Policies as Tests](https://www.pulumi.com/docs/idp/best-practices/patterns/policies-as-tests)**: Validation logic ensures compliance
- **[Cost Control](https://www.pulumi.com/docs/idp/best-practices/patterns/cost-control-using-components-policies-constrained-inputs)**: Constrained inputs and policies prevent resource over-provisioning
- **[Security Updates](https://www.pulumi.com/docs/idp/best-practices/patterns/security-updates-using-components)**: Centralized component updates for security patches

### Configuration Management

- Use `StackSettings` in `config.py` for structured configuration loading
- Override per-environment values in `Pulumi.<stack>.yaml`
- Avoid hard-coding values; use configuration for all environment-specific settings

### Infrastructure Organization

**`components/`** - Generic, reusable AWS primitives:
- Technology-focused thin wrappers (VPC, ECS, RDS, SQS)
- Functions returning dataclasses
- Independently importable without `__init__.py` re-exports
- Examples: `sqs_fifo.py`, `ecs_helpers.py`, `rds_postgres.py`

**`modules/`** - Application-specific infrastructure bundles:
- Compose multiple components with application logic
- Include Dagster, TaskIQ, and other app-specific concerns
- Examples: `dagster.py` (complete deployment), `taskiq.py` (queues + workers + IAM)

**Guideline**: Reusable across projects → `components/`. Application-specific → `modules/`.

## Getting Started

1. Install prerequisites: Pulumi CLI, Python dependencies via `uv`
2. Launch LocalStack: `docker compose up -d localstack`
3. Deploy infrastructure: `mise run up`
4. Build and push images: `./scripts/build-and-push.sh`

### TaskIQ Demo Configuration

The TaskIQ demo module is optional and disabled by default. Enable and configure it with:

```sh
cd deploy
uv run pulumi config set --path taskiqDemo.enabled true --stack local
uv run pulumi config set --path taskiqDemo.queueName taskiq-demo --stack local
uv run pulumi config set --path taskiqDemo.imageTag taskiq-demo --stack local
uv run pulumi config set --path taskiqDemo.apiDesiredCount 1 --stack local
uv run pulumi config set --path taskiqDemo.workerDesiredCount 1 --stack local
cd ..
```

Then build and push the image and apply the stack:

```sh
mise run push:taskiq-demo
mise run demo:taskiq
```

Pulumi exports additional outputs when the module is enabled (`taskiqDemoQueueUrl`, `taskiqDemoApiServiceName`, `taskiqDemoWorkerServiceName`, and `taskiqDemoSecurityGroupId`) to simplify troubleshooting.

## Commands

- `mise run up` - Deploy infrastructure
- `mise run preview` - Preview changes
- `mise run destroy` - Destroy infrastructure
- `mise run refresh` - Refresh state from cloud
- `mise run demo:taskiq` - Build/push the TaskIQ demo image and deploy the stack (requires `taskiqDemo.enabled=true`)

## Additional Resources

- [Pulumi IDP Best Practices](https://www.pulumi.com/docs/idp/best-practices/)
- [Four Factors Framework](https://www.pulumi.com/docs/idp/best-practices/four-factors)
- [Pulumi Configuration](https://www.pulumi.com/docs/iac/concepts/config/)
