"""Tests for Dagster schedules."""

from __future__ import annotations

import pytest
from dagster import DefaultScheduleStatus

from dagster_taskiq.dagster_jobs.schedules import get_all_schedules, get_testing_schedules


class TestProductionSchedules:
    """Test production schedule definitions."""

    def test_get_all_schedules_count(self):
        """Test that all expected schedules are returned."""
        schedules = get_all_schedules()
        assert len(schedules) == 5

    def test_get_all_schedules_names(self):
        """Test that all schedules have expected names."""
        schedules = get_all_schedules()
        schedule_names = {schedule.name for schedule in schedules}
        
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
    def test_schedule_job_mapping(self, schedule_name: str, expected_job_name: str):
        """Test that schedules are mapped to correct jobs."""
        schedules = get_all_schedules()
        schedule_dict = {schedule.name: schedule for schedule in schedules}
        
        assert schedule_name in schedule_dict
        schedule = schedule_dict[schedule_name]
        assert schedule.job.name == expected_job_name

    def test_production_schedule_configuration(self):
        """Test that production schedules have correct configuration."""
        schedules = get_all_schedules()
        
        for schedule in schedules:
            # All production schedules should run every 10 minutes
            assert schedule.cron_schedule == "*/10 * * * *"
            # All production schedules should be running by default
            assert schedule.default_status == DefaultScheduleStatus.RUNNING
            # All should have descriptions
            assert schedule.description is not None
            assert len(schedule.description) > 0

    def test_schedule_descriptions(self):
        """Test that schedules have meaningful descriptions."""
        schedules = get_all_schedules()
        
        for schedule in schedules:
            description = schedule.description.lower()
            # Should mention the job type
            job_type = schedule.job.name.replace("_job", "").replace("_", " ")
            assert any(word in description for word in job_type.split())
            # Should mention timing
            assert "10 minutes" in description


class TestTestingSchedules:
    """Test testing schedule definitions."""

    def test_get_testing_schedules_count(self):
        """Test that testing schedules are returned."""
        schedules = get_testing_schedules()
        assert len(schedules) == 2

    def test_get_testing_schedules_names(self):
        """Test that testing schedules have expected names."""
        schedules = get_testing_schedules()
        schedule_names = {schedule.name for schedule in schedules}
        
        expected_names = {
            "test_fast_job_schedule",
            "test_mixed_job_schedule",
        }
        
        assert schedule_names == expected_names

    def test_testing_schedule_configuration(self):
        """Test that testing schedules have correct configuration."""
        schedules = get_testing_schedules()
        
        for schedule in schedules:
            # All testing schedules should run every 2 minutes
            assert schedule.cron_schedule == "*/2 * * * *"
            # All testing schedules should be stopped by default
            assert schedule.default_status == DefaultScheduleStatus.STOPPED
            # All should have descriptions
            assert schedule.description is not None
            assert "test" in schedule.description.lower()
            assert "2 minutes" in schedule.description.lower()

    @pytest.mark.parametrize(
        ("schedule_name", "expected_job_name"),
        [
            ("test_fast_job_schedule", "fast_job"),
            ("test_mixed_job_schedule", "mixed_job"),
        ],
    )
    def test_testing_schedule_job_mapping(self, schedule_name: str, expected_job_name: str):
        """Test that testing schedules are mapped to correct jobs."""
        schedules = get_testing_schedules()
        schedule_dict = {schedule.name: schedule for schedule in schedules}
        
        assert schedule_name in schedule_dict
        schedule = schedule_dict[schedule_name]
        assert schedule.job.name == expected_job_name


class TestScheduleIntegration:
    """Test schedule integration and consistency."""

    def test_schedule_job_references_valid(self):
        """Test that all schedule job references are valid."""
        all_schedules = get_all_schedules() + get_testing_schedules()
        
        for schedule in all_schedules:
            # Job should have a name
            assert schedule.job.name is not None
            assert len(schedule.job.name) > 0
            
            # Job should be executable (has ops)
            assert len(schedule.job.op_defs) > 0

    def test_no_duplicate_schedule_names(self):
        """Test that there are no duplicate schedule names across all schedules."""
        production_schedules = get_all_schedules()
        testing_schedules = get_testing_schedules()
        
        production_names = {schedule.name for schedule in production_schedules}
        testing_names = {schedule.name for schedule in testing_schedules}
        
        # No overlap between production and testing schedule names
        assert len(production_names & testing_names) == 0
        
        # No duplicates within each set
        assert len(production_names) == len(production_schedules)
        assert len(testing_names) == len(testing_schedules)