# TaskIQ Demo

Minimal TaskIQ deployment that targets LocalStack SQS. The project exposes a FastAPI ingress service for enqueueing sleep jobs and a TaskIQ worker that consumes the queue.

## Local Setup

1. Copy `.env.example` to `.env` and adjust values if needed. Defaults target LocalStack at `http://localhost:4566`.
2. Install dependencies via `uv`:
   ```sh
   uv sync
   ```
3. Run the API locally:
   ```sh
   uv run taskiq-demo-api
   ```
   The service listens on `http://localhost:8000` by default. Submit work with:
   ```sh
   curl -X POST http://localhost:8000/tasks -H 'content-type: application/json' -d '{"duration_seconds": 5}'
   ```
4. Run the worker in a second terminal:
   ```sh
   uv run taskiq-demo-worker
   ```

Alternatively, use Mise tasks:
```sh
mise run app
mise run worker
```

## Container Image

The Docker image uses a shared entrypoint that dispatches on `SERVICE_ROLE` (`api` or `worker`). Build via the project-wide Bake target:
```sh
docker buildx bake taskiq-demo
```

## Testing

Run linters and tests with Mise:
```sh
mise run lint
mise run test
```

Or run pytest directly:
```sh
uv run pytest
```

## Deployment with Pulumi

1. Enable the demo module in Pulumi config (values can be adjusted per environment):
   ```sh
   cd deploy
   uv run pulumi config set --path taskiqDemo.enabled true --stack local
   uv run pulumi config set --path taskiqDemo.queueName taskiq-demo --stack local
   uv run pulumi config set --path taskiqDemo.imageTag taskiq-demo --stack local
   uv run pulumi config set --path taskiqDemo.apiDesiredCount 1 --stack local
   uv run pulumi config set --path taskiqDemo.workerDesiredCount 1 --stack local
   cd ..
   ```
2. Start LocalStack if it is not already running and deploy the stack:
   ```sh
   mise run demo:taskiq
   ```
   The task builds the `taskiq-demo` image, pushes it to LocalStack ECR, runs `pulumi up`, and prints the stack outputs.

## Manual Verification

After the stack is deployed, obtain the API endpoint and submit a job:

```sh
# Capture helper values from Pulumi outputs
mise -C deploy run pulumi:outputs

# Example using the default stack names (run from the deploy/ directory)
cd deploy
CLUSTER="dagster-taskiq-demo-local"
API_SERVICE=$(uv run pulumi stack output taskiqDemoApiServiceName --stack local)
TASK_ARN=$(awslocal ecs list-tasks --cluster "${CLUSTER}" --service-name "${API_SERVICE}" --query 'taskArns[0]' --output text)
ENI_ID=$(awslocal ecs describe-tasks --cluster "${CLUSTER}" --tasks "${TASK_ARN}" --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value | [0]' --output text)
API_IP=$(awslocal ec2 describe-network-interfaces --network-interface-ids "${ENI_ID}" --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
cd ..

curl "http://${API_IP}:8000/health"
curl -X POST "http://${API_IP}:8000/tasks" -H 'content-type: application/json' -d '{"duration_seconds": 8}'
```

Confirm the worker processes the request:
```sh
awslocal logs tail '/aws/ecs/taskiq-demo-worker-local' --since 5m
```

You can also inspect the queue depth:
```sh
QUEUE_URL=$(cd deploy && uv run pulumi stack output taskiqDemoQueueUrl --stack local)
awslocal sqs get-queue-attributes --queue-url "${QUEUE_URL}" --attribute-names ApproximateNumberOfMessages
```
