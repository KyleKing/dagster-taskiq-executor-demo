# TaskIQ Demo

Minimal TaskIQ deployment targeting LocalStack SQS with FastAPI ingress service and TaskIQ worker for sleep job processing.

## Quick Start

### Local Development

1. **Configure environment**:
   ```bash
   cp .env.example .env
   # Defaults target LocalStack at http://localhost:4566
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Run services**:
   ```bash
   # Terminal 1: API service
   uv run taskiq-demo-api
   # Listens on http://localhost:8000

   # Terminal 2: Worker
   uv run taskiq-demo-worker
   ```

4. **Submit jobs**:
   ```bash
   curl -X POST http://localhost:8000/tasks \
     -H 'content-type: application/json' \
     -d '{"duration_seconds": 5}'
   ```

**Or use Mise tasks**:
```bash
mise run app    # Start API
mise run worker # Start worker
```

### Container Deployment

Build via project-wide Bake target:
```bash
docker buildx bake taskiq-demo
```

Image uses shared entrypoint dispatching on `SERVICE_ROLE` (`api` or `worker`).

## Testing

```bash
mise run lint    # Lint code
mise run test    # Run tests
uv run pytest    # Direct pytest
```

## Pulumi Deployment

1. **Enable demo module**:
   ```bash
   cd deploy
   uv run pulumi config set --path taskiqDemo.enabled true --stack local
   uv run pulumi config set --path taskiqDemo.queueName taskiq-demo --stack local
   uv run pulumi config set --path taskiqDemo.imageTag taskiq-demo --stack local
   uv run pulumi config set --path taskiqDemo.apiDesiredCount 1 --stack local
   uv run pulumi config set --path taskiqDemo.workerDesiredCount 1 --stack local
   cd ..
   ```

2. **Deploy stack**:
   ```bash
   mise run demo:taskiq
   ```
   Builds image, pushes to LocalStack ECR, runs `pulumi up`, prints outputs.

## Verification

### API Testing

```bash
# Get API endpoint from deployed stack
cd deploy
CLUSTER="dagster-taskiq-demo-local"
API_SERVICE=$(uv run pulumi stack output taskiqDemoApiServiceName --stack local)
TASK_ARN=$(awslocal ecs list-tasks --cluster "${CLUSTER}" --service-name "${API_SERVICE}" --query 'taskArns[0]' --output text)
ENI_ID=$(awslocal ecs describe-tasks --cluster "${CLUSTER}" --tasks "${TASK_ARN}" --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value | [0]' --output text)
API_IP=$(awslocal ec2 describe-network-interfaces --network-interface-ids "${ENI_ID}" --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
cd ..

# Test API
curl "http://${API_IP}:8000/health"
curl -X POST "http://${API_IP}:8000/tasks" \
  -H 'content-type: application/json' \
  -d '{"duration_seconds": 8}'
```

### Worker Monitoring

```bash
# Check worker logs
awslocal logs tail '/aws/ecs/taskiq-demo-worker-local' --since 5m

# Check queue depth
QUEUE_URL=$(cd deploy && uv run pulumi stack output taskiqDemoQueueUrl --stack local)
awslocal sqs get-queue-attributes \
  --queue-url "${QUEUE_URL}" \
  --attribute-names ApproximateNumberOfMessages
```

## Architecture

- **FastAPI Service**: HTTP ingress for job submission
- **TaskIQ Worker**: Consumes SQS messages and processes sleep jobs
- **LocalStack**: Provides SQS queue and ECS infrastructure
- **Docker**: Containerized deployment with role-based entrypoint

## Configuration

Environment variables in `.env`:
- `AWS_DEFAULT_REGION`: AWS region (default: us-east-1)
- `SQS_QUEUE_NAME`: TaskIQ queue name
- `LOCALSTACK_ENDPOINT`: LocalStack URL (default: http://localhost:4566)
