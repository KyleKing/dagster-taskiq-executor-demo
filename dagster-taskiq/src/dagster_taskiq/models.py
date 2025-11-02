# Modifications copyright (c) 2024 dagster-taskiq contributors

"""Database operations for TaskIQ executor idempotency."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from dagster_taskiq.task_payloads import IdempotencyRecord, TaskState


class IdempotencyStorage(ABC):
    """Abstract base class for persistent storage of idempotency records."""

    @abstractmethod
    def get_record(self, idempotency_key: str) -> IdempotencyRecord | None:
        """Get idempotency record by key."""
        pass

    @abstractmethod
    def save_record(self, record: IdempotencyRecord) -> None:
        """Save or update idempotency record."""
        pass

    @abstractmethod
    def update_state(self, idempotency_key: str, state: TaskState, result_data: str | None = None) -> None:
        """Update the state of an idempotency record."""
        pass

    @abstractmethod
    def is_completed(self, idempotency_key: str) -> bool:
        """Check if a task is already completed."""
        pass


class InMemoryIdempotencyStorage(IdempotencyStorage):
    """In-memory implementation of idempotency storage for testing."""

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self.records: dict[str, IdempotencyRecord] = {}

    def get_record(self, idempotency_key: str) -> IdempotencyRecord | None:
        """Get idempotency record by key."""
        return self.records.get(idempotency_key)

    def save_record(self, record: IdempotencyRecord) -> None:
        """Save or update idempotency record."""
        self.records[record.idempotency_key] = record

    def update_state(self, idempotency_key: str, state: TaskState, result_data: str | None = None) -> None:
        """Update the state of an idempotency record."""
        if record := self.records.get(idempotency_key):
            record.update_state(state, result_data)

    def is_completed(self, idempotency_key: str) -> bool:
        """Check if a task is already completed."""
        record = self.records.get(idempotency_key)
        return record is not None and record.state == TaskState.COMPLETED


# Global instance - lazy initialization
_idempotency_storage: IdempotencyStorage | None = None


def get_idempotency_storage() -> IdempotencyStorage:
    """Get the global idempotency storage instance."""
    global _idempotency_storage
    if _idempotency_storage is None:
        _idempotency_storage = InMemoryIdempotencyStorage()
    return _idempotency_storage


def set_idempotency_storage(storage: IdempotencyStorage) -> None:
    """Set the global idempotency storage instance."""
    global _idempotency_storage
    _idempotency_storage = storage