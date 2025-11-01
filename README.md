# LocalStack ECS + SQS Sandbox

This repository bootstraps a LocalStack container preconfigured with ECS and SQS so you can prototype AWS integrations locally.

## Prerequisites
- Docker Desktop (or compatible Docker engine)
- Optional: `awslocal` (`pip install awscli-local`) for interacting with LocalStack from the host
- Optional: LocalStack API key (`LOCALSTACK_AUTH_TOKEN`) if you need Pro-only ECS features

## Usage
1. Start LocalStack
   ```bash
   docker compose up --build
   ```
2. On the first startup LocalStack runs `localstack/init/10_init_resources.sh`, which creates:
   - An SQS queue (defaults to `demo-queue`)
   - An ECS cluster (defaults to `demo-cluster`)

   Repeat starts are idempotent; existing resources are left in place.

3. Interact with the emulated services
   ```bash
   awslocal sqs list-queues
   awslocal ecs list-clusters
   ```

4. Stop and clean up
   ```bash
   docker compose down
   ```

## Pulumi Deployment
1. Ensure LocalStack is running (see above).
2. Provision resources with Pulumi via `uv`:
   ```bash
   cd deploy
   uv sync
   # Use the local stack (passphrase: 'localstack')
   PULUMI_CONFIG_PASSPHRASE=localstack uv run pulumi up --stack local
   ```
   The stack configurations (`Pulumi.local.yaml`) point the AWS provider at `http://localhost:4566` and seed demo names for the ECS cluster and SQS queue.

3. Update configuration as needed, for example:
   ```bash
   PULUMI_CONFIG_PASSPHRASE=localstack uv run pulumi config set queueName my-queue --stack local
   PULUMI_CONFIG_PASSPHRASE=localstack uv run pulumi up --stack local
   ```

## Configuration
- `AWS_DEFAULT_REGION` (default `us-east-1`) controls the region used by LocalStack.
- `LOCALSTACK_SQS_QUEUE_NAME` overrides the queue created during initialization.
- `LOCALSTACK_ECS_CLUSTER_NAME` overrides the cluster created during initialization.
- Set `LOCALSTACK_PERSISTENCE=0` to disable persistent state between restarts.

Update these variables in your shell environment or in a `.env` file that Docker Compose can load.

## Notes
- ECS support requires Docker access inside the LocalStack container. The compose file mounts the host Docker socket for this purpose.
- Some ECS APIs require a LocalStack Pro license. Provide a `LOCALSTACK_AUTH_TOKEN` if you need those endpoints.
