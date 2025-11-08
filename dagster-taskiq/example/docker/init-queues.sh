#!/bin/bash
# Initialize SQS queues and S3 bucket in LocalStack for dagster-taskiq example

set -e

# Load environment variables
if [ -f docker.env ]; then
    set -a
    source docker.env
    set +a
fi

# Extract queue name from URL
QUEUE_URL="${DAGSTER_TASKIQ_SQS_QUEUE_URL:-http://localstack:4566/000000000000/dagster-tasks}"
ENDPOINT_URL="${DAGSTER_TASKIQ_SQS_ENDPOINT_URL:-http://localstack:4566}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
BUCKET_NAME="${DAGSTER_TASKIQ_S3_BUCKET_NAME:-dagster-taskiq-results}"

# Extract queue name from URL (format: http://endpoint/account-id/queue-name)
QUEUE_NAME=$(echo "$QUEUE_URL" | sed 's|.*/||')
CANCEL_QUEUE_NAME="${QUEUE_NAME}-cancels"

echo "Initializing LocalStack resources..."
echo "  Queue URL: $QUEUE_URL"
echo "  Queue Name: $QUEUE_NAME"
echo "  Cancel Queue Name: $CANCEL_QUEUE_NAME"
echo "  S3 Bucket: $BUCKET_NAME"
echo "  Endpoint: $ENDPOINT_URL"
echo "  Region: $REGION"

# Wait for LocalStack to be ready
echo "Waiting for LocalStack to be ready..."
until curl -s "$ENDPOINT_URL/_localstack/health" > /dev/null 2>&1; do
    echo "  Waiting for LocalStack..."
    sleep 2
done
echo "LocalStack is ready!"

# Create SQS queues
echo "Creating SQS queues..."
aws --endpoint-url="$ENDPOINT_URL" \
    --region "$REGION" \
    sqs create-queue \
    --queue-name "$QUEUE_NAME" \
    || echo "  Queue '$QUEUE_NAME' may already exist"

aws --endpoint-url="$ENDPOINT_URL" \
    --region "$REGION" \
    sqs create-queue \
    --queue-name "$CANCEL_QUEUE_NAME" \
    || echo "  Cancel queue '$CANCEL_QUEUE_NAME' may already exist"

# Create S3 bucket
echo "Creating S3 bucket..."
aws --endpoint-url="$ENDPOINT_URL" \
    --region "$REGION" \
    s3 mb "s3://$BUCKET_NAME" \
    || echo "  Bucket '$BUCKET_NAME' may already exist"

echo "Initialization complete!"

