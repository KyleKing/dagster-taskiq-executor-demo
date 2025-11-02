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


class PostgreSQLIdempotencyStorage(IdempotencyStorage):
    """Persistent storage for idempotency records using PostgreSQL."""

    def __init__(self, connection_string: str) -> None:
        """Initialize PostgreSQL idempotency storage."""
        import psycopg2.pool

        self.pool = psycopg2.pool.SimpleConnectionPool(1, 10, connection_string)
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensure the idempotency table exists."""
        with self.pool.getconn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS taskiq_idempotency_records (
                        idempotency_key VARCHAR(255) PRIMARY KEY,
                        state VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        task_data TEXT,
                        result_data TEXT
                    )
                """)
            conn.commit()
        self.pool.putconn(conn)

    def get_record(self, idempotency_key: str) -> IdempotencyRecord | None:
        """Get idempotency record by key."""
        with self.pool.getconn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM taskiq_idempotency_records WHERE idempotency_key = %s", (idempotency_key,)
                )
                result = cursor.fetchone()
                if result:
                    return IdempotencyRecord(
                        idempotency_key=result[0],
                        state=TaskState(result[1]),
                        created_at=result[2],
                        updated_at=result[3],
                        task_data=result[4],
                        result_data=result[5],
                    )
        self.pool.putconn(conn)
        return None

    def save_record(self, record: IdempotencyRecord) -> None:
        """Save or update idempotency record."""
        with self.pool.getconn() as conn:
            with conn.cursor() as cursor:
                # Try to insert first
                try:
                    cursor.execute(
                        """
                        INSERT INTO taskiq_idempotency_records
                        (idempotency_key, state, created_at, updated_at, task_data, result_data)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                        (
                            record.idempotency_key,
                            record.state.value,
                            record.created_at,
                            record.updated_at,
                            record.task_data,
                            record.result_data,
                        ),
                    )
                except Exception:
                    # Update if insert failed (key exists)
                    cursor.execute(
                        """
                        UPDATE taskiq_idempotency_records
                        SET state = %s, updated_at = %s, task_data = %s, result_data = %s
                        WHERE idempotency_key = %s
                    """,
                        (
                            record.state.value,
                            record.updated_at,
                            record.task_data,
                            record.result_data,
                            record.idempotency_key,
                        ),
                    )
            conn.commit()
        self.pool.putconn(conn)

    def update_state(self, idempotency_key: str, state: TaskState, result_data: str | None = None) -> None:
        """Update the state of an idempotency record."""
        with self.pool.getconn() as conn:
            with conn.cursor() as cursor:
                if result_data is not None:
                    cursor.execute(
                        """
                        UPDATE taskiq_idempotency_records
                        SET state = %s, updated_at = %s, result_data = %s
                        WHERE idempotency_key = %s
                    """,
                        (state.value, datetime.now(UTC), result_data, idempotency_key),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE taskiq_idempotency_records
                        SET state = %s, updated_at = %s
                        WHERE idempotency_key = %s
                    """,
                        (state.value, datetime.now(UTC), idempotency_key),
                    )
            conn.commit()
        self.pool.putconn(conn)

    def is_completed(self, idempotency_key: str) -> bool:
        """Check if a task is already completed."""
        record = self.get_record(idempotency_key)
        return record is not None and record.state == TaskState.COMPLETED