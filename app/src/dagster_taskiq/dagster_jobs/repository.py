"""Dagster repository definitions."""

from dagster import Definitions

from dagster_taskiq.taskiq_executor import taskiq_executor

from .jobs import fast_job, mixed_job, parallel_fast_job, sequential_slow_job, slow_job
from .schedules import get_all_schedules

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
    executor=taskiq_executor,
)
