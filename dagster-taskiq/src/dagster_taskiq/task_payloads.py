# Modifications copyright (c) 2024 dagster-taskiq contributors

"""Task payload models for Dagster TaskIQ execution."""

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskState(enum.StrEnum):
    """Task execution states."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OpExecutionTask(BaseModel):
    """Task payload for executing a Dagster op."""

    run_id: str = Field(description="Dagster run ID")
    step_keys_to_execute: list[str] = Field(description="Step keys to execute")
    instance_ref_dict: dict[str, Any] = Field(description="Serialized instance reference")
    reconstructable_job_dict: dict[str, Any] = Field(description="Reconstructable job dict")
    retry_mode_dict: dict[str, Any] = Field(description="Retry mode configuration")
    known_state_dict: dict[str, Any] | None = Field(default=None, description="Known execution state")

    @property
    def idempotency_key(self) -> str:
        """Generate unique idempotency key for this task."""
        return f"{self.run_id}:{','.join(self.step_keys_to_execute)}"

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "OpExecutionTask":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class ExecutionResult(BaseModel):
    """Result of task execution."""

    run_id: str = Field(description="Dagster run ID")
    step_key: str = Field(description="Dagster step key")
    state: TaskState = Field(description="Final execution state")
    output: Any = Field(default=None, description="Op output value")
    error: str | None = Field(default=None, description="Error message if failed")
    started_at: datetime | None = Field(default=None, description="Task start timestamp")
    completed_at: datetime | None = Field(default=None, description="Task completion timestamp")
    execution_time_seconds: float | None = Field(default=None, description="Total execution time")

    @property
    def idempotency_key(self) -> str:
        """Generate unique idempotency key for this result."""
        return f"{self.run_id}:{self.step_key}"

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "ExecutionResult":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


class IdempotencyRecord(BaseModel):
    """Record for tracking task idempotency."""

    idempotency_key: str = Field(description="Unique key for idempotency")
    state: TaskState = Field(description="Current task state")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Record creation time")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Last update time")
    task_data: str | None = Field(default=None, description="Serialized task data")
    result_data: str | None = Field(default=None, description="Serialized result data")

    def update_state(self, new_state: TaskState, result_data: str | None = None) -> None:
        """Update the task state and timestamp."""
        self.state = new_state
        self.updated_at = datetime.now(UTC)
        if result_data is not None:
            self.result_data = result_data

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "IdempotencyRecord":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)