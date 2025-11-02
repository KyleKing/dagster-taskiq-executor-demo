"""Tests for Dagster repository definitions."""

from __future__ import annotations

import pytest
from dagster import JobDefinition, ScheduleDefinition

from dagster_taskiq.dagster_jobs.repository import defs


class TestRepositoryDefinitions:
    """Test the main repository definitions."""

    def test_repository_has_jobs(self):
        """Test that repository contains expected jobs."""
        jobs = defs.get_job_defs()
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

    def test_repository_has_schedules(self):
        """Test that repository contains expected schedules."""
        schedules = defs.get_schedule_defs()
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

    def test_all_jobs_are_job_definitions(self):
        """Test that all jobs are proper JobDefinition instances."""
        jobs = defs.get_job_defs()
        
        for job in jobs:
            assert isinstance(job, JobDefinition)
            assert job.name is not None
            assert len(job.name) > 0

    def test_all_schedules_are_schedule_definitions(self):
        """Test that all schedules are proper ScheduleDefinition instances."""
        schedules = defs.get_schedule_defs()
        
        for schedule in schedules:
            assert isinstance(schedule, ScheduleDefinition)
            assert schedule.name is not None
            assert len(schedule.name) > 0

    def test_schedule_job_references_exist(self):
        """Test that all schedules reference jobs that exist in the repository."""
        jobs = defs.get_job_defs()
        schedules = defs.get_schedule_defs()
        
        job_names = {job.name for job in jobs}
        
        for schedule in schedules:
            schedule_job_name = schedule.job.name
            assert schedule_job_name in job_names, f"Schedule {schedule.name} references non-existent job {schedule_job_name}"

    def test_repository_completeness(self):
        """Test that repository contains all expected components."""
        # Should have jobs
        assert len(defs.get_job_defs()) > 0
        
        # Should have schedules
        assert len(defs.get_schedule_defs()) > 0
        
        # Should not have assets (this is a job-based repository)
        assert len(defs.get_asset_defs()) == 0
        
        # Should not have sensors (using schedules instead)
        assert len(defs.get_sensor_defs()) == 0

    @pytest.mark.parametrize(
        "job_name",
        ["fast_job", "slow_job", "mixed_job", "parallel_fast_job", "sequential_slow_job"],
    )
    def test_individual_job_accessibility(self, job_name: str):
        """Test that individual jobs can be accessed from the repository."""
        jobs = defs.get_job_defs()
        job_dict = {job.name: job for job in jobs}
        
        assert job_name in job_dict
        job = job_dict[job_name]
        
        # Job should be executable
        assert len(job.op_defs) > 0
        
        # Job should have description
        assert job.description is not None
        assert len(job.description) > 0

    @pytest.mark.parametrize(
        "schedule_name",
        ["fast_job_schedule", "slow_job_schedule", "mixed_job_schedule", "parallel_fast_job_schedule", "sequential_slow_job_schedule"],
    )
    def test_individual_schedule_accessibility(self, schedule_name: str):
        """Test that individual schedules can be accessed from the repository."""
        schedules = defs.get_schedule_defs()
        schedule_dict = {schedule.name: schedule for schedule in schedules}
        
        assert schedule_name in schedule_dict
        schedule = schedule_dict[schedule_name]
        
        # Schedule should have valid cron schedule
        assert schedule.cron_schedule is not None
        assert len(schedule.cron_schedule) > 0
        
        # Schedule should have description
        assert schedule.description is not None
        assert len(schedule.description) > 0