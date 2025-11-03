"""Dagster repository definitions."""

from dagster import Definitions
from dagster_taskiq import taskiq_executor

from dagster_taskiq_demo.config.settings import settings

from .jobs import fast_job, mixed_job, parallel_fast_job, sequential_slow_job, slow_job
from .schedules import get_all_schedules

# Configure the taskiq executor for LocalStack
configured_taskiq_executor = taskiq_executor.configured({
    "queue_url": f"{settings.aws_endpoint_url}/000000000000/{settings.taskiq_queue_name}",
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
