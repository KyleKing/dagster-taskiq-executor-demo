"""Tests for Dagster job definitions and execution."""

from __future__ import annotations

import pytest
from dagster import DagsterInstance, materialize
from dagster.core.execution.api import create_execution_plan
from dagster.core.snap import JobSnapshot

from dagster_taskiq.dagster_jobs.jobs import (
    fast_job,
    mixed_job,
    parallel_fast_job,
    sequential_slow_job,
    slow_job,
)


class TestJobDefinitions:
    """Test job definitions and structure."""

    @pytest.mark.parametrize(
        ("job", "expected_name", "expected_description_contains"),
        [
            (fast_job, "fast_job", "fast async operations"),
            (slow_job, "slow_job", "slow async operations"),
            (mixed_job, "mixed_job", "both fast and slow"),
            (parallel_fast_job, "parallel_fast_job", "multiple parallel fast"),
            (sequential_slow_job, "sequential_slow_job", "sequential slow"),
        ],
    )
    def test_job_metadata(self, job, expected_name: str, expected_description_contains: str):
        """Test that jobs have correct metadata."""
        assert job.name == expected_name
        assert expected_description_contains in job.description.lower()

    def test_fast_job_structure(self):
        """Test fast job has correct op structure."""
        execution_plan = create_execution_plan(fast_job)
        step_keys = {step.key for step in execution_plan.steps}
        
        assert "fast_async_op" in step_keys
        assert "data_processing_op" in step_keys
        assert len(step_keys) == 2

    def test_slow_job_structure(self):
        """Test slow job has correct op structure."""
        execution_plan = create_execution_plan(slow_job)
        step_keys = {step.key for step in execution_plan.steps}
        
        assert "slow_async_op" in step_keys
        assert "data_processing_op" in step_keys
        assert len(step_keys) == 2

    def test_mixed_job_structure(self):
        """Test mixed job has correct op structure."""
        execution_plan = create_execution_plan(mixed_job)
        step_keys = {step.key for step in execution_plan.steps}
        
        assert "fast_async_op" in step_keys
        assert "slow_async_op" in step_keys
        assert "data_processing_op" in step_keys
        assert "aggregation_op" in step_keys
        assert len(step_keys) == 5  # 2 data_processing_op instances + 3 others

    def test_parallel_fast_job_structure(self):
        """Test parallel fast job has correct op structure."""
        execution_plan = create_execution_plan(parallel_fast_job)
        step_keys = {step.key for step in execution_plan.steps}
        
        # Should have 3 fast ops and 3 processing ops
        fast_ops = [key for key in step_keys if "fast_op" in key]
        process_ops = [key for key in step_keys if "process" in key]
        
        assert len(fast_ops) == 3
        assert len(process_ops) == 3
        assert len(step_keys) == 6

    def test_sequential_slow_job_structure(self):
        """Test sequential slow job has correct op structure."""
        execution_plan = create_execution_plan(sequential_slow_job)
        step_keys = {step.key for step in execution_plan.steps}
        
        # Should have 2 slow ops, 2 processing ops, and 1 aggregation op
        slow_ops = [key for key in step_keys if "slow_op" in key]
        process_ops = [key for key in step_keys if "process" in key]
        
        assert len(slow_ops) == 2
        assert len(process_ops) == 2
        assert "aggregation_op" in step_keys
        assert len(step_keys) == 5


class TestJobExecution:
    """Test job execution with mocked operations."""

    def test_fast_job_execution(self, dagster_instance: DagsterInstance, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time):
        """Test fast job executes successfully."""
        result = materialize([fast_job], instance=dagster_instance)
        
        assert result.success
        assert len(result.asset_materializations_for_node("fast_async_op")) == 0  # ops don't create assets
        
        # Verify the job ran to completion
        run_records = dagster_instance.get_run_records()
        assert len(run_records) == 1
        assert run_records[0].dagster_run.status.name == "SUCCESS"

    def test_slow_job_execution(self, dagster_instance: DagsterInstance, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time):
        """Test slow job executes successfully."""
        result = materialize([slow_job], instance=dagster_instance)
        
        assert result.success
        
        # Verify the job ran to completion
        run_records = dagster_instance.get_run_records()
        assert len(run_records) == 1
        assert run_records[0].dagster_run.status.name == "SUCCESS"

    def test_mixed_job_execution(self, dagster_instance: DagsterInstance, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time):
        """Test mixed job executes successfully."""
        # Mock time to return different values for different operations
        mock_loop_time.side_effect = [
            1000.0, 1020.0,  # fast_async_op
            2000.0, 2300.0,  # slow_async_op  
            3000.0,          # data_processing_op calls
            4000.0,          # aggregation_op call
        ]
        
        result = materialize([mixed_job], instance=dagster_instance)
        
        assert result.success
        
        # Verify the job ran to completion
        run_records = dagster_instance.get_run_records()
        assert len(run_records) == 1
        assert run_records[0].dagster_run.status.name == "SUCCESS"

    def test_parallel_fast_job_execution(self, dagster_instance: DagsterInstance, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time):
        """Test parallel fast job executes successfully."""
        result = materialize([parallel_fast_job], instance=dagster_instance)
        
        assert result.success
        
        # Verify the job ran to completion
        run_records = dagster_instance.get_run_records()
        assert len(run_records) == 1
        assert run_records[0].dagster_run.status.name == "SUCCESS"

    def test_sequential_slow_job_execution(self, dagster_instance: DagsterInstance, mock_asyncio_sleep, mock_secrets_randbelow, mock_loop_time):
        """Test sequential slow job executes successfully."""
        result = materialize([sequential_slow_job], instance=dagster_instance)
        
        assert result.success
        
        # Verify the job ran to completion
        run_records = dagster_instance.get_run_records()
        assert len(run_records) == 1
        assert run_records[0].dagster_run.status.name == "SUCCESS"


class TestJobSnapshots:
    """Test job snapshots for serialization and metadata."""

    @pytest.mark.parametrize(
        "job",
        [fast_job, slow_job, mixed_job, parallel_fast_job, sequential_slow_job],
    )
    def test_job_snapshot_creation(self, job):
        """Test that job snapshots can be created successfully."""
        snapshot = JobSnapshot.from_job_def(job)
        
        assert snapshot.name == job.name
        assert snapshot.description == job.description
        assert len(snapshot.node_defs_snaps) > 0
        assert snapshot.lineage_snapshot is not None