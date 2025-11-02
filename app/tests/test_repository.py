"""Tests for Dagster repository definitions."""

from __future__ import annotations

from typing import cast

import pytest
from dagster import JobDefinition, ScheduleDefinition

from dagster_taskiq.dagster_jobs.repository import defs


def _job_defs() -> tuple[JobDefinition, ...]:
    jobs = tuple(defs.jobs or ())
    for job in jobs:
        assert isinstance(job, JobDefinition)
    return cast("tuple[JobDefinition, ...]", jobs)


def _schedule_defs() -> tuple[ScheduleDefinition, ...]:
    schedules = tuple(defs.schedules or ())
    for schedule in schedules:
        assert isinstance(schedule, ScheduleDefinition)
    return cast("tuple[ScheduleDefinition, ...]", schedules)


def test_repository_has_jobs() -> None:
    """Repository contains expected jobs."""
    jobs = _job_defs()
    job_names = {job.name for job in jobs}

    expected_jobs = {
        "fast_job",
        "slow_job",
        "mixed_job",
        "parallel_fast_job",
        "sequential_slow_job",
    }

    assert job_names == expected_jobs
    assert len(jobs) == 5


def test_repository_has_schedules() -> None:
    """Repository contains expected schedules."""
    schedules = _schedule_defs()
    schedule_names = {schedule.name for schedule in schedules}

    expected_schedules = {
        "fast_job_schedule",
        "slow_job_schedule",
        "mixed_job_schedule",
        "parallel_fast_job_schedule",
        "sequential_slow_job_schedule",
    }

    assert schedule_names == expected_schedules
    assert len(schedules) == 5


def test_all_jobs_are_job_definitions() -> None:
    """Jobs are proper JobDefinition instances."""
    for job in _job_defs():
        assert job.name


def test_all_schedules_are_schedule_definitions() -> None:
    """Schedules are proper ScheduleDefinition instances."""
    for schedule in _schedule_defs():
        assert schedule.name


def test_schedule_job_references_exist() -> None:
    """Schedules reference jobs that exist in the repository."""
    job_names = {job.name for job in _job_defs()}

    for schedule in _schedule_defs():
        job_def = schedule.job
        assert isinstance(job_def, JobDefinition)
        assert job_def.name in job_names, f"Schedule {schedule.name} references non-existent job {job_def.name}"


def test_repository_completeness() -> None:
    """Repository contains expected components."""
    assert len(_job_defs()) > 0
    assert len(_schedule_defs()) > 0

    assets = tuple(defs.assets or ())
    sensors = tuple(defs.sensors or ())

    assert not assets
    assert not sensors


@pytest.mark.parametrize(
    "job_name",
    ["fast_job", "slow_job", "mixed_job", "parallel_fast_job", "sequential_slow_job"],
)
def test_individual_job_accessibility(job_name: str) -> None:
    """Individual jobs are accessible from the repository."""
    job_dict = {job.name: job for job in _job_defs()}

    assert job_name in job_dict
    job = job_dict[job_name]

    assert len(job.top_level_node_defs) > 0
    assert job.description


@pytest.mark.parametrize(
    "schedule_name",
    [
        "fast_job_schedule",
        "slow_job_schedule",
        "mixed_job_schedule",
        "parallel_fast_job_schedule",
        "sequential_slow_job_schedule",
    ],
)
def test_individual_schedule_accessibility(schedule_name: str) -> None:
    """Individual schedules are accessible and configured."""
    schedule_dict = {schedule.name: schedule for schedule in _schedule_defs()}

    assert schedule_name in schedule_dict
    schedule = schedule_dict[schedule_name]

    assert schedule.cron_schedule
    assert schedule.description
    job_def = schedule.job
    assert isinstance(job_def, JobDefinition)
