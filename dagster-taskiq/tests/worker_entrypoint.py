from __future__ import annotations

import os

import boto3


def main() -> None:
    # Ensure the SQS queue exists
    queue_url = os.getenv("DAGSTER_TASKIQ_SQS_QUEUE_URL")
    if queue_url:
        # Extract queue name from URL
        queue_name = queue_url.split("/")[-1]
        sqs = boto3.client(
            "sqs",
            endpoint_url=os.getenv("DAGSTER_TASKIQ_SQS_ENDPOINT_URL"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        )
        try:
            # Check if queue exists
            sqs.get_queue_url(QueueName=queue_name)
        except sqs.exceptions.QueueDoesNotExist:
            # Create the queue if it doesn't exist
            sqs.create_queue(QueueName=queue_name)
            # Also create the cancel queue
            cancel_queue_name = f"{queue_name}-cancels"
            sqs.create_queue(QueueName=cancel_queue_name)

    # Ensure the S3 bucket exists
    bucket_name = os.getenv("DAGSTER_TASKIQ_S3_BUCKET_NAME")
    if bucket_name:
        s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("DAGSTER_TASKIQ_S3_ENDPOINT_URL"),
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        )
        try:
            s3.head_bucket(Bucket=bucket_name)
        except s3.exceptions.NoSuchBucket:
            s3.create_bucket(Bucket=bucket_name)

    from dagster_taskiq.cli import main as dagster_taskiq_main

    dagster_taskiq_main()


if __name__ == "__main__":
    main()
