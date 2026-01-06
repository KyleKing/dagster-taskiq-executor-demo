# Pulumi Infrastructure Deployment

Infrastructure as code for deploying the Dagster TaskIQ demo on AWS using Pulumi.

## Architecture

Follows the [Four Factors Framework](https://www.pulumi.com/docs/idp/best-practices/four-factors):

- **Templates**: Reusable code patterns in `components/` and `modules/`
- **Components**: Encapsulated AWS resources (ECS clusters, RDS instances)
- **Environments**: Configuration via `Pulumi.<stack>.yaml` files

## Directory Structure

**`components/`** - Generic, reusable AWS primitives:

- Technology-focused thin wrappers (VPC, ECS, RDS, SQS)
- Examples: `sqs_fifo.py`, `ecs_helpers.py`, `rds_postgres.py`

**`modules/`** - Application-specific infrastructure bundles:

- Compose multiple components with application logic
- Examples: `dagster.py`, `taskiq.py`

## Prerequisites

- AWS CLI configured with credentials
- Pulumi CLI (`brew install pulumi`)
- Python dependencies via `uv`

## Quick Start

1. **Initialize stack**:

   ```bash
   cd deploy
   uv sync --all-groups
   uv run pulumi stack init dev
   ```

2. **Configure stack** (edit `Pulumi.dev.yaml` or use CLI):

   ```bash
   uv run pulumi config set aws:region us-east-1 --stack dev
   ```

3. **Deploy**:

   ```bash
   uv run pulumi up --stack dev
   ```

4. **Build and push images**:

   ```bash
   cd ..
   ./scripts/build-and-push.sh
   cd deploy && uv run pulumi up --stack dev
   ```

## Commands

```bash
# From deploy/ directory
mise run :pulumi:up        # Deploy infrastructure
mise run :pulumi:preview   # Preview changes
mise run :pulumi:down      # Destroy infrastructure (use with caution)
mise run :pulumi:refresh   # Refresh state from cloud
mise run :pulumi:outputs   # Show stack outputs
```

## Configuration

Uses `StackSettings` in `config.py` for structured configuration. Override per-environment values in `Pulumi.<stack>.yaml`.

## Stack Outputs

Get infrastructure URLs and identifiers:

```bash
uv run pulumi stack output queueUrl --stack dev
uv run pulumi stack output databaseEndpoint --stack dev
uv run pulumi stack output clusterName --stack dev
uv run pulumi stack output --stack dev  # All outputs
```

## Observability

From project root:

```bash
mise run logs:dagster-daemon
mise run logs:taskiq-worker
mise run aws:services
mise run ecs:status SERVICE_NAME=taskiq-worker
mise run queue:depth
```

## Troubleshooting

### Common Issues

**Pulumi locks stuck**:

```bash
pulumi cancel
```

**State drift** (Pulumi state out of sync):

```bash
mise run :pulumi:refresh
```

## Best Practices

- **Preview before deploying**: `mise run :pulumi:preview`
- **Use separate stacks** for dev/staging/prod
- **Don't modify resources outside Pulumi**
- **Incremental changes** over large refactors

## Additional Resources

- [Pulumi IDP Best Practices](https://www.pulumi.com/docs/idp/best-practices/)
- [Pulumi Configuration](https://www.pulumi.com/docs/iac/concepts/config/)
- [Pulumi State Management](https://www.pulumi.com/docs/iac/concepts/state/)
