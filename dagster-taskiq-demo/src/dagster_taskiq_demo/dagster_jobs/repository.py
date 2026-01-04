"""Dagster repository definitions."""

import os

from dagster import Definitions
from dagster_taskiq import taskiq_executor

from dagster_taskiq_demo.config.settings import settings

from .jobs import fast_job, mixed_job, parallel_fast_job, sequential_slow_job, slow_job
from .schedules import get_all_schedules


def _build_queue_url() -> str:
    """Build the SQS queue URL based on environment configuration."""
    if env_url := os.getenv("DAGSTER_TASKIQ_SQS_QUEUE_URL"):
        return env_url
    if settings.aws_endpoint_url:
        return f"{settings.aws_endpoint_url}/000000000000/{settings.taskiq_queue_name}"
    account_id = os.getenv("AWS_ACCOUNT_ID", "123456789012")
    return f"https://sqs.{settings.aws_region}.amazonaws.com/{account_id}/{settings.taskiq_queue_name}"


# Configure the taskiq executor
configured_taskiq_executor = taskiq_executor.configured({
    "queue_url": _build_queue_url(),
    "region_name": settings.aws_region,
    "endpoint_url": settings.aws_endpoint_url,
})

# Main repository with all jobs and schedules
defs = Definitions(
    jobs=[
        fast_job,
        slow_job,
        mixed_job,
        parallel_fast_job,
        sequential_slow_job,
    ],
    schedules=get_all_schedules(),
    executor=configured_taskiq_executor,
)
