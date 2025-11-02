# LocalStack ECS + SQS Sandbox

This repository bootstraps a LocalStack container preconfigured with ECS and SQS so you can prototype AWS integrations locally.

## Prerequisites
- `mise` (`brew install mise` and `mise install`) - manages tool versions (pulumi, uv, etc.)
- Docker Desktop (or compatible Docker engine)
- `awslocal` CLI (`uvx awscli-local` or `mise use pipx:awscli-local`) - **required** for pushing Docker images to LocalStack ECR
- LocalStack Pro API key (`LOCALSTACK_AUTH_TOKEN`) to unlock ECS, RDS, Cloud Map, and ALB emulation

## Usage
1. Set your LocalStack Pro token in `.env`
   ```bash
   cp .env.example .env
   nvim .env
   ```
2. Start LocalStack
   ```bash
   docker compose up -d localstack
   ```

3. The LocalStack web UI is now available at: <https://app.localstack.cloud>. Interact with the emulated services
   ```bash
   awslocal sqs list-queues
   awslocal ecs list-clusters
   ```

4. Stop and clean up
   ```bash
   docker compose down
   ```

## Pulumi Deployment

### Initial Setup

1. Ensure LocalStack is running:
   ```bash
   docker compose up -d localstack
   ```

2. Deploy the infrastructure:
   ```bash
   cd deploy
   uv run pulumi up --yes --stack local
   ```
   This creates the ECR repository and other AWS resources. The stack configuration (`Pulumi.local.yaml`) targets LocalStack at `http://localstack:4566`.

3. Build and push the application Docker image to LocalStack ECR:
   ```bash
   ./scripts/build-and-push.sh
   ```
   This uses Docker Bake to build the application image and pushes it to the ECR repository created in step 2.

### Development Workflow

**Application code changes:**
```bash
./scripts/build-and-push.sh  # Rebuild and push the image with Docker Bake
# Update ECS services to pull the new image (manual restart or update task definition)
```

**Infrastructure changes:**
```bash
cd deploy
uv run pulumi up --yes --stack local
```

**Configuration updates:**
```bash
cd deploy
uv run pulumi config set queueName my-queue --stack local
uv run pulumi up --yes --stack local
```

## Configuration
- `AWS_DEFAULT_REGION` (default `us-east-1`) controls the region used by LocalStack.
- `LOCALSTACK_SQS_QUEUE_NAME` overrides the queue created during initialization.
- `LOCALSTACK_ECS_CLUSTER_NAME` overrides the cluster created during initialization.
- Set `LOCALSTACK_PERSISTENCE=0` to disable persistent state between restarts.

Update these variables in your shell environment or in a `.env` file that Docker Compose can load.

## Notes
- **Docker Bake**: Uses Docker Bake (see `docker-bake.hcl`) for declarative, reproducible container image builds
- **Image Build Separation**: Docker images are built and pushed separately from Pulumi using `./scripts/build-and-push.sh` and the `awslocal` CLI. This avoids networking complexity with Pulumi's docker-build provider and uses LocalStack's well-tested workflow.
- **Local Pulumi**: Pulumi runs directly on your machine (no Docker container needed) - just use `cd deploy && uv run pulumi <command>`
- ECS support requires Docker access inside the LocalStack container. The compose file mounts the host Docker socket for this purpose.
- LocalStack Pro is required for all ECS, RDS, Service Discovery, and Application Load Balancer APIs used in this demo. Without a valid `LOCALSTACK_AUTH_TOKEN` Pulumi will fail with `InvalidClientTokenId` or `InternalFailure` responses from LocalStack.
