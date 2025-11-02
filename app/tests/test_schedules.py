"""Tests for Dagster schedules."""

from __future__ import annotations

import pytest
from dagster import DefaultScheduleStatus, JobDefinition, ScheduleDefinition

from dagster_taskiq_demo.dagster_jobs.schedules import get_all_schedules, get_testing_schedules


def _production_schedules() -> tuple[ScheduleDefinition, ...]:
    schedules = tuple(get_all_schedules())
    for schedule in schedules:
        assert isinstance(schedule, ScheduleDefinition)
    return schedules


def _testing_schedules() -> tuple[ScheduleDefinition, ...]:
    schedules = tuple(get_testing_schedules())
    for schedule in schedules:
        assert isinstance(schedule, ScheduleDefinition)
    return schedules


def test_get_all_schedules_count() -> None:
    """All expected production schedules are returned."""
    assert len(_production_schedules()) == 5


def test_get_all_schedules_names() -> None:
    """Production schedules expose expected names."""
    schedule_names = {schedule.name for schedule in get_all_schedules()}
    expected_names = {
        "fast_job_schedule",
        "slow_job_schedule",
        "mixed_job_schedule",
        "parallel_fast_job_schedule",
        "sequential_slow_job_schedule",
    }
    assert schedule_names == expected_names


@pytest.mark.parametrize(
    ("schedule_name", "expected_job_name"),
    [
        ("fast_job_schedule", "fast_job"),
        ("slow_job_schedule", "slow_job"),
        ("mixed_job_schedule", "mixed_job"),
        ("parallel_fast_job_schedule", "parallel_fast_job"),
        ("sequential_slow_job_schedule", "sequential_slow_job"),
    ],
)
def test_schedule_job_mapping(schedule_name: str, expected_job_name: str) -> None:
    """Production schedules map to the correct jobs."""
    schedule_dict = {schedule.name: schedule for schedule in _production_schedules()}
    assert schedule_name in schedule_dict
    job_def = schedule_dict[schedule_name].job
    assert isinstance(job_def, JobDefinition)
    assert job_def.name == expected_job_name


def test_production_schedule_configuration() -> None:
    """Production schedules share cadence and status."""
    for schedule in _production_schedules():
        assert schedule.cron_schedule == "*/10 * * * *"
        assert schedule.default_status == DefaultScheduleStatus.RUNNING
        assert schedule.description


def test_schedule_descriptions() -> None:
    """Production schedule descriptions mention job intent and cadence."""
    for schedule in _production_schedules():
        description = schedule.description
        assert description is not None
        job_def = schedule.job
        assert isinstance(job_def, JobDefinition)
        job_type = job_def.name.replace("_job", "").replace("_", " ")
        description_lower = description.lower()
        assert any(word in description_lower for word in job_type.split())
        assert "10 minutes" in description_lower


def test_get_testing_schedules_count() -> None:
    """Testing schedules are exposed for CI."""
    assert len(_testing_schedules()) == 2


def test_get_testing_schedules_names() -> None:
    """Testing schedules expose expected names."""
    schedule_names = {schedule.name for schedule in _testing_schedules()}
    expected_names = {"test_fast_job_schedule", "test_mixed_job_schedule"}
    assert schedule_names == expected_names


def test_testing_schedule_configuration() -> None:
    """Testing schedules share cadence and default status."""
    for schedule in _testing_schedules():
        assert schedule.cron_schedule == "*/2 * * * *"
        assert schedule.default_status == DefaultScheduleStatus.STOPPED
        description = schedule.description
        assert description is not None
        description_lower = description.lower()
        assert "test" in description_lower
        assert "2 minutes" in description_lower


@pytest.mark.parametrize(
    ("schedule_name", "expected_job_name"),
    [
        ("test_fast_job_schedule", "fast_job"),
        ("test_mixed_job_schedule", "mixed_job"),
    ],
)
def test_testing_schedule_job_mapping(schedule_name: str, expected_job_name: str) -> None:
    """Testing schedules map to the correct jobs."""
    schedule_dict = {schedule.name: schedule for schedule in _testing_schedules()}
    assert schedule_name in schedule_dict
    job_def = schedule_dict[schedule_name].job
    assert isinstance(job_def, JobDefinition)
    assert job_def.name == expected_job_name


def test_schedule_job_references_valid() -> None:
    """All schedules reference runnable jobs."""
    all_schedules = _production_schedules() + _testing_schedules()
    for schedule in all_schedules:
        job_def = schedule.job
        assert isinstance(job_def, JobDefinition)
        assert job_def.name
        assert len(job_def.top_level_node_defs) > 0


def test_no_duplicate_schedule_names() -> None:
    """Schedule names are unique across production and testing."""
    production_schedules = get_all_schedules()
    testing_schedules = get_testing_schedules()

    production_names = {schedule.name for schedule in production_schedules}
    testing_names = {schedule.name for schedule in testing_schedules}

    assert not production_names & testing_names
    assert len(production_names) == len(production_schedules)
    assert len(testing_names) == len(testing_schedules)
