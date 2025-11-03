import os

# SQS configuration
sqs_queue_url = os.getenv(
    "DAGSTER_TASKIQ_SQS_QUEUE_URL",
    "https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks",
)

sqs_endpoint_url = os.getenv("DAGSTER_TASKIQ_SQS_ENDPOINT_URL")  # For LocalStack

aws_region_name = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# Task configuration
task_default_priority = 5

task_default_queue = "dagster"

# Worker configuration
worker_max_messages = 1

wait_time_seconds = 20  # Long polling

visibility_timeout = 300  # 5 minutes
