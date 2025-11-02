"""Tests for Dagster job definitions and execution."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any

import pytest
from dagster import DagsterInstance, JobDefinition

from dagster_taskiq_demo.dagster_jobs.jobs import (
    fast_job,
    mixed_job,
    parallel_fast_job,
    sequential_slow_job,
    slow_job,
)

FAST_OP_CONFIG: dict[str, Any] = {
    "base_duration": 1,
    "variance": 0,
    "sleep_interval": 0.0,
}
SLOW_OP_CONFIG: dict[str, Any] = {
    "base_duration": 1,
    "variance": 0,
    "min_duration": 1,
    "sleep_interval": 0.0,
}

JOB_RUN_CONFIGS: dict[str, dict[str, Any]] = {
    "fast_job": {
        "ops": {
            "fast_async_op": {"config": FAST_OP_CONFIG},
        },
    },
    "slow_job": {
        "ops": {
            "slow_async_op": {"config": SLOW_OP_CONFIG},
        },
    },
    "mixed_job": {
        "ops": {
            "fast_async_op": {"config": FAST_OP_CONFIG},
            "slow_async_op": {"config": SLOW_OP_CONFIG},
        },
    },
    "parallel_fast_job": {
        "ops": {
            "fast_op_1": {"config": FAST_OP_CONFIG},
            "fast_op_2": {"config": FAST_OP_CONFIG},
            "fast_op_3": {"config": FAST_OP_CONFIG},
        },
    },
    "sequential_slow_job": {
        "ops": {
            "slow_op_1": {"config": SLOW_OP_CONFIG},
            "slow_op_2": {"config": SLOW_OP_CONFIG},
        },
    },
}


def _job_run_config(job_name: str) -> dict[str, Any]:
    config = JOB_RUN_CONFIGS.get(job_name)
    return deepcopy(config) if config else {}


@pytest.mark.parametrize(
    ("job_def", "expected_name", "expected_description_contains"),
    [
        (fast_job, "fast_job", "fast async operations"),
        (slow_job, "slow_job", "slow async operations"),
        (mixed_job, "mixed_job", "both fast and slow"),
        (parallel_fast_job, "parallel_fast_job", "multiple parallel fast"),
        (sequential_slow_job, "sequential_slow_job", "sequential slow"),
    ],
)
def test_job_metadata(job_def: JobDefinition, expected_name: str, expected_description_contains: str) -> None:
    """Jobs expose expected names and descriptions."""
    assert job_def.name == expected_name
    description = job_def.description
    assert description is not None
    assert expected_description_contains in description.lower()


@pytest.mark.parametrize(
    ("job_def", "expected_nodes"),
    [
        (fast_job, Counter(["fast_async_op", "data_processing_op"])),
        (slow_job, Counter(["slow_async_op", "data_processing_op"])),
        (
            mixed_job,
            Counter(["fast_async_op", "slow_async_op", "data_processing_op", "data_processing_op_2", "aggregation_op"]),
        ),
        (
            parallel_fast_job,
            Counter(["fast_op_1", "fast_op_2", "fast_op_3", "process_1", "process_2", "process_3"]),
        ),
        (
            sequential_slow_job,
            Counter(["slow_op_1", "slow_op_2", "process_1", "process_2", "aggregation_op"]),
        ),
    ],
)
def test_job_graph_structure(job_def: JobDefinition, expected_nodes: Counter[str]) -> None:
    """Jobs wire expected ops and aliases."""
    assert Counter(job_def.graph.node_names()) == expected_nodes


@pytest.mark.parametrize(
    "job_def",
    [fast_job, slow_job, mixed_job, parallel_fast_job, sequential_slow_job],
)
def test_job_execution_succeeds(
    dagster_instance: DagsterInstance,
    job_def: JobDefinition,
) -> None:
    """Jobs execute successfully via execute_in_process."""
    run_config = _job_run_config(job_def.name)
    result = job_def.execute_in_process(instance=dagster_instance, run_config=run_config)

    assert result.success
    assert result.dagster_run.status.name == "SUCCESS"

    run_records = dagster_instance.get_run_records()
    assert len(run_records) == 1
    assert run_records[0].dagster_run.status.name == "SUCCESS"
