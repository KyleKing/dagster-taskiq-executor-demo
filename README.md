# LocalStack ECS + SQS Sandbox

This repository bootstraps a LocalStack container preconfigured with ECS and SQS so you can prototype AWS integrations locally.

## Prerequisites
- Docker Desktop (or compatible Docker engine)
- Optional: `awslocal` (`pip install awscli-local`) for interacting with LocalStack from the host
- LocalStack Pro API key (`LOCALSTACK_AUTH_TOKEN`) to unlock ECS, RDS, Cloud Map, and ALB emulation

## Usage
1. Set your LocalStack Pro token in `.env`
   ```bash
   cp .env.example .env
   nvim .env
   ```
2. Build and start LocalStack plus the Pulumi workspace container
   ```bash
   docker compose up --build localstack pulumi
   ```
   The Pulumi container (_pulumi-deploy_) stays running so you can execute `uv` and `pulumi` commands inside a consistent environment.
3. The LocalStack web UI is now available at: <https://app.localstack.cloud>. Interact with the emulated services
   ```bash
   awslocal sqs list-queues
   awslocal ecs list-clusters
   ```

5. Stop and clean up
   ```bash
   docker compose down
   ```

## Pulumi Deployment
1. Ensure the `localstack` and `pulumi` services are running:
   ```bash
   docker compose up -d localstack pulumi
   ```
2. Preview or apply the stack from inside the Pulumi container:
   ```bash
   docker compose exec pulumi uv run pulumi preview --yes --non-interactive --stack local
   docker compose exec pulumi uv run pulumi up --yes --non-interactive --stack local
   ```
   The container already has dependencies installed through `uv sync`, and the stack configuration (`Pulumi.local.yaml`) targets LocalStack at `http://localstack:4566`.

3. Update configuration as needed, for example:
   ```bash
   docker compose exec pulumi uv run pulumi config set queueName my-queue --stack local
   docker compose exec pulumi uv run pulumi up --yes --non-interactive --stack local
   ```

## Configuration
- `AWS_DEFAULT_REGION` (default `us-east-1`) controls the region used by LocalStack.
- `LOCALSTACK_SQS_QUEUE_NAME` overrides the queue created during initialization.
- `LOCALSTACK_ECS_CLUSTER_NAME` overrides the cluster created during initialization.
- Set `LOCALSTACK_PERSISTENCE=0` to disable persistent state between restarts.

Update these variables in your shell environment or in a `.env` file that Docker Compose can load.

## Notes
- ECS support requires Docker access inside the LocalStack container. The compose file mounts the host Docker socket for this purpose.
- LocalStack Pro is required for all ECS, RDS, Service Discovery, and Application Load Balancer APIs used in this demo. Without a valid `LOCALSTACK_AUTH_TOKEN` Pulumi will fail with `InvalidClientTokenId` or `InternalFailure` responses from LocalStack.
