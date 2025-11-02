"""Dagster schedules for running jobs every ten minutes."""

from __future__ import annotations

from dagster import DefaultScheduleStatus, ScheduleDefinition

from .jobs import fast_job, mixed_job, parallel_fast_job, sequential_slow_job, slow_job


def get_all_schedules() -> list[ScheduleDefinition]:
    """Get all job schedules for production deployment.

    Returns:
        List of all schedule definitions for production use.
    """
    return [
        ScheduleDefinition(
            name="fast_job_schedule",
            job=fast_job,
            cron_schedule="*/10 * * * *",  # Every 10 minutes
            default_status=DefaultScheduleStatus.RUNNING,
            description="Run fast job every 10 minutes",
        ),
        ScheduleDefinition(
            name="slow_job_schedule",
            job=slow_job,
            cron_schedule="*/10 * * * *",  # Every 10 minutes
            default_status=DefaultScheduleStatus.RUNNING,
            description="Run slow job every 10 minutes",
        ),
        ScheduleDefinition(
            name="mixed_job_schedule",
            job=mixed_job,
            cron_schedule="*/10 * * * *",  # Every 10 minutes
            default_status=DefaultScheduleStatus.RUNNING,
            description="Run mixed job every 10 minutes",
        ),
        ScheduleDefinition(
            name="parallel_fast_job_schedule",
            job=parallel_fast_job,
            cron_schedule="*/10 * * * *",  # Every 10 minutes
            default_status=DefaultScheduleStatus.RUNNING,
            description="Run parallel fast job every 10 minutes",
        ),
        ScheduleDefinition(
            name="sequential_slow_job_schedule",
            job=sequential_slow_job,
            cron_schedule="*/10 * * * *",  # Every 10 minutes
            default_status=DefaultScheduleStatus.RUNNING,
            description="Run sequential slow job every 10 minutes",
        ),
    ]


def get_testing_schedules() -> list[ScheduleDefinition]:
    """Get schedules for testing with shorter intervals.

    Returns:
        List of schedule definitions for testing with 2-minute intervals.
    """
    return [
        ScheduleDefinition(
            name="test_fast_job_schedule",
            job=fast_job,
            cron_schedule="*/2 * * * *",  # Every 2 minutes for testing
            default_status=DefaultScheduleStatus.STOPPED,
            description="Test fast job every 2 minutes",
        ),
        ScheduleDefinition(
            name="test_mixed_job_schedule",
            job=mixed_job,
            cron_schedule="*/2 * * * *",  # Every 2 minutes for testing
            default_status=DefaultScheduleStatus.STOPPED,
            description="Test mixed job every 2 minutes",
        ),
    ]
