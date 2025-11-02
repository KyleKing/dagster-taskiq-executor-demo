"""Exactly-once verification tooling for load simulation."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from dagster_taskiq_demo.config.settings import Settings
from dagster_taskiq_demo.taskiq_executor.models import get_idempotency_storage
from dagster_taskiq_demo.taskiq_executor.task_payloads import TaskState

logger = structlog.get_logger(__name__)


@dataclass
class VerificationResult:
    """Result of exactly-once verification."""

    total_runs: int
    completed_runs: int
    failed_runs: int
    pending_runs: int
    duplicate_executions: int
    missing_executions: int
    run_details: list[RunVerificationDetail]


@dataclass
class RunVerificationDetail:
    """Detailed verification for a single run."""

    run_id: str
    job_name: str
    submitted_at: str
    status: str
    expected_steps: int
    completed_steps: int
    failed_steps: int
    duplicate_steps: int
    missing_steps: int
    step_details: list[StepVerificationDetail]


@dataclass
class StepVerificationDetail:
    """Verification detail for a single step."""

    step_key: str
    idempotency_key: str
    expected: bool
    found: bool
    state: str | None
    duplicates: int


class ExactlyOnceVerifier:
    """Verifies exactly-once execution semantics for load-simulated runs."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the verifier."""
        self.settings = settings
        self.idempotency_storage = get_idempotency_storage()

    def verify_idempotency_records(self, scenario_tag: str | None = None) -> VerificationResult:
        """Verify exactly-once execution by analyzing idempotency records.

        Args:
            scenario_tag: Optional scenario tag to filter records

        Returns:
            Verification results
        """
        # Get all idempotency records
        all_records = self._get_all_idempotency_records()

        # Filter for load simulator records if scenario specified
        if scenario_tag:
            # For now, we'll check all records since we don't store scenario info in idempotency
            # In a real implementation, we'd store scenario metadata
            pass

        logger.info("verifying_idempotency_records", total_records=len(all_records))

        # Group records by run_id
        run_groups = self._group_records_by_run(all_records)

        run_details = []
        total_completed = 0
        total_failed = 0
        total_pending = 0
        total_duplicates = 0
        total_missing = 0

        for run_id, records in run_groups.items():
            run_detail = self._verify_run_records(run_id, records)
            run_details.append(run_detail)

            if run_detail.status == "completed":
                total_completed += 1
            elif run_detail.status == "failed":
                total_failed += 1
            elif run_detail.status == "pending":
                total_pending += 1

            total_duplicates += run_detail.duplicate_steps
            total_missing += run_detail.missing_steps

        result = VerificationResult(
            total_runs=len(run_groups),
            completed_runs=total_completed,
            failed_runs=total_failed,
            pending_runs=total_pending,
            duplicate_executions=total_duplicates,
            missing_executions=total_missing,
            run_details=run_details,
        )

        logger.info(
            "verification_complete",
            total_runs=result.total_runs,
            completed_runs=result.completed_runs,
            failed_runs=result.failed_runs,
            pending_runs=result.pending_runs,
            duplicate_executions=result.duplicate_executions,
            missing_executions=result.missing_executions,
        )

        return result

    def _get_all_idempotency_records(self) -> list[Any]:
        """Get all idempotency records from storage."""
        # This is a simplified implementation - in practice you'd need to query the database
        # For now, we'll return an empty list since we don't have a method to get all records
        # TODO: Add method to IdempotencyStorage to get all records
        logger.warning("get_all_idempotency_records_not_implemented")
        return []

    def _group_records_by_run(self, records: list[Any]) -> dict[str, list[Any]]:
        """Group idempotency records by run_id."""
        run_groups = {}
        for record in records:
            # Extract run_id from idempotency_key (format: "run_id:step_keys")
            idempotency_key = record.idempotency_key
            if ":" in idempotency_key:
                run_id = idempotency_key.split(":")[0]
                if run_id not in run_groups:
                    run_groups[run_id] = []
                run_groups[run_id].append(record)
        return run_groups

    def _verify_run_records(self, run_id: str, records: list[Any]) -> RunVerificationDetail:
        """Verify records for a single run."""
        # Group records by step
        step_records = {}
        for record in records:
            idempotency_key = record.idempotency_key
            if ":" in idempotency_key:
                parts = idempotency_key.split(":")
                if len(parts) >= 2:
                    step_keys = parts[1].split(",")
                    for step_key in step_keys:
                        if step_key not in step_records:
                            step_records[step_key] = []
                        step_records[step_key].append(record)

        # Verify each step
        step_details = []
        completed_steps = 0
        failed_steps = 0
        duplicate_steps = 0
        missing_steps = 0

        for step_key, step_recs in step_records.items():
            # Check for duplicates (multiple completion records for same step)
            completed_count = sum(1 for r in step_recs if r.state == TaskState.COMPLETED)
            failed_count = sum(1 for r in step_recs if r.state == TaskState.FAILED)

            duplicates = max(0, completed_count - 1)  # More than 1 completion is duplicate
            duplicate_steps += duplicates

            found = len(step_recs) > 0
            if not found:
                missing_steps += 1

            state = None
            if completed_count > 0:
                state = TaskState.COMPLETED.value
                completed_steps += 1
            elif failed_count > 0:
                state = TaskState.FAILED.value
                failed_steps += 1
            elif step_recs:
                state = step_recs[0].state.value

            step_detail = StepVerificationDetail(
                step_key=step_key,
                idempotency_key=f"{run_id}:{step_key}",
                expected=True,  # Assume all steps are expected
                found=found,
                state=state,
                duplicates=duplicates,
            )
            step_details.append(step_detail)

        # Determine overall run status
        total_steps = len(step_records)
        if completed_steps == total_steps and total_steps > 0:
            status = "completed"
        elif failed_steps > 0:
            status = "failed"
        elif completed_steps > 0:
            status = "partial"
        else:
            status = "pending"

        return RunVerificationDetail(
            run_id=run_id,
            job_name="unknown",  # We don't store job name in idempotency records
            submitted_at="",  # We don't store submission time in idempotency records
            status=status,
            expected_steps=total_steps,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            duplicate_steps=duplicate_steps,
            missing_steps=missing_steps,
            step_details=step_details,
        )

    def _verify_single_run(self, run: dict[str, Any]) -> RunVerificationDetail:
        """Verify exactly-once execution for a single run."""
        run_id = run["runId"]
        job_name = run["jobName"]
        submitted_at = run.get("startTime", "")

        # Get expected steps for this job
        expected_steps = self._get_expected_steps_for_job(job_name)

        # Check idempotency records for each expected step
        step_details = []
        completed_steps = 0
        failed_steps = 0
        duplicate_steps = 0
        missing_steps = 0

        for step_key in expected_steps:
            idempotency_key = f"{run_id}:{step_key}"
            step_detail = self._verify_step_execution(idempotency_key, step_key)
            step_details.append(step_detail)

            if step_detail.found:
                if step_detail.state == TaskState.COMPLETED.value:
                    completed_steps += 1
                elif step_detail.state == TaskState.FAILED.value:
                    failed_steps += 1

            if step_detail.duplicates > 0:
                duplicate_steps += step_detail.duplicates
            if not step_detail.found:
                missing_steps += 1

        # Determine overall run status
        if completed_steps == len(expected_steps):
            status = "completed"
        elif failed_steps > 0:
            status = "failed"
        elif completed_steps > 0:
            status = "partial"
        else:
            status = "pending"

        return RunVerificationDetail(
            run_id=run_id,
            job_name=job_name,
            submitted_at=submitted_at,
            status=status,
            expected_steps=len(expected_steps),
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            duplicate_steps=duplicate_steps,
            missing_steps=missing_steps,
            step_details=step_details,
        )

    def _get_expected_steps_for_job(self, job_name: str) -> list[str]:
        """Get expected step keys for a job."""
        # This is a simplified mapping - in practice you'd query Dagster for job structure
        job_step_mapping = {
            "fast_job": ["fast_async_op", "data_processing_op"],
            "slow_job": ["slow_async_op", "data_processing_op"],
            "mixed_job": ["fast_async_op", "slow_async_op", "data_processing_op", "data_processing_op_2", "aggregation_op"],
            "parallel_fast_job": ["fast_op_1", "fast_op_2", "fast_op_3", "process_1", "process_2", "process_3"],
            "sequential_slow_job": ["slow_op_1", "slow_op_2", "process_1", "process_2", "aggregation_op"],
        }
        return job_step_mapping.get(job_name, [])

    def _verify_step_execution(self, idempotency_key: str, step_key: str) -> StepVerificationDetail:
        """Verify execution of a single step."""
        record = self.idempotency_storage.get_record(idempotency_key)

        if record:
            # Check for duplicates by looking for multiple completion records
            # This is a simplified check - in practice you'd need more sophisticated duplicate detection
            duplicates = 0  # TODO: Implement duplicate detection logic

            return StepVerificationDetail(
                step_key=step_key,
                idempotency_key=idempotency_key,
                expected=True,
                found=True,
                state=record.state.value,
                duplicates=duplicates,
            )
        else:
            return StepVerificationDetail(
                step_key=step_key,
                idempotency_key=idempotency_key,
                expected=True,
                found=False,
                state=None,
                duplicates=0,
            )

    def export_report(self, result: VerificationResult, output_path: Path, format: str = "json") -> None:
        """Export verification results to file.

        Args:
            result: Verification results
            output_path: Path to output file
            format: Export format ('json' or 'csv')
        """
        if format == "json":
            self._export_json_report(result, output_path)
        elif format == "csv":
            self._export_csv_report(result, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _export_json_report(self, result: VerificationResult, output_path: Path) -> None:
        """Export results as JSON."""
        data = {
            "summary": {
                "total_runs": result.total_runs,
                "completed_runs": result.completed_runs,
                "failed_runs": result.failed_runs,
                "pending_runs": result.pending_runs,
                "duplicate_executions": result.duplicate_executions,
                "missing_executions": result.missing_executions,
            },
            "runs": [
                {
                    "run_id": detail.run_id,
                    "job_name": detail.job_name,
                    "submitted_at": detail.submitted_at,
                    "status": detail.status,
                    "expected_steps": detail.expected_steps,
                    "completed_steps": detail.completed_steps,
                    "failed_steps": detail.failed_steps,
                    "duplicate_steps": detail.duplicate_steps,
                    "missing_steps": detail.missing_steps,
                    "steps": [
                        {
                            "step_key": step.step_key,
                            "idempotency_key": step.idempotency_key,
                            "expected": step.expected,
                            "found": step.found,
                            "state": step.state,
                            "duplicates": step.duplicates,
                        }
                        for step in detail.step_details
                    ],
                }
                for detail in result.run_details
            ],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("exported_json_report", path=str(output_path))

    def _export_csv_report(self, result: VerificationResult, output_path: Path) -> None:
        """Export results as CSV."""
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "run_id", "job_name", "submitted_at", "status",
                "expected_steps", "completed_steps", "failed_steps",
                "duplicate_steps", "missing_steps"
            ])

            for detail in result.run_details:
                writer.writerow([
                    detail.run_id,
                    detail.job_name,
                    detail.submitted_at,
                    detail.status,
                    detail.expected_steps,
                    detail.completed_steps,
                    detail.failed_steps,
                    detail.duplicate_steps,
                    detail.missing_steps,
                ])

        logger.info("exported_csv_report", path=str(output_path))