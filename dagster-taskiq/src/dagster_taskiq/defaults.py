"""Default configuration values for dagster-taskiq.

This module provides default values for SQS queues, regions, and other configuration
that can be overridden via environment variables.
"""

import os

# SQS configuration
sqs_queue_url = os.getenv(
    "DAGSTER_TASKIQ_SQS_QUEUE_URL",
    "https://sqs.us-east-1.amazonaws.com/123456789012/dagster-tasks",
)

sqs_endpoint_url = os.getenv("DAGSTER_TASKIQ_SQS_ENDPOINT_URL")  # For LocalStack

aws_region_name = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# S3 configuration for extended messages and results
s3_bucket_name = os.getenv("DAGSTER_TASKIQ_S3_BUCKET_NAME", "dagster-taskiq-results")
s3_endpoint_url = os.getenv("DAGSTER_TASKIQ_S3_ENDPOINT_URL")  # For LocalStack

# Task configuration
task_default_priority = 5

task_default_queue = "dagster"

# Worker configuration
worker_max_messages = 1

wait_time_seconds = 20  # Long polling
