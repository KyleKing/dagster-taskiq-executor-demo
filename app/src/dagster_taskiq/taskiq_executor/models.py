"""Database operations for TaskIQ executor idempotency."""

from datetime import UTC, datetime

from dagster_taskiq.config.database import get_database_manager
from dagster_taskiq.taskiq_executor.task_payloads import IdempotencyRecord, TaskState


class IdempotencyStorage:
    """Persistent storage for idempotency records using PostgreSQL."""

    def __init__(self) -> None:
        """Initialize idempotency storage."""
        self.db_manager = get_database_manager()
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Ensure the idempotency table exists."""
        with self.db_manager.get_connection() as conn:
            conn.execute("""
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

    def get_record(self, idempotency_key: str) -> IdempotencyRecord | None:
        """Get idempotency record by key."""
        with self.db_manager.get_connection() as conn:
            result = conn.execute(
                "SELECT * FROM taskiq_idempotency_records WHERE idempotency_key = %s", (idempotency_key,)
            ).fetchone()
            if result:
                return IdempotencyRecord(
                    idempotency_key=result[0],
                    state=TaskState(result[1]),
                    created_at=result[2],
                    updated_at=result[3],
                    task_data=result[4],
                    result_data=result[5],
                )
        return None

    def save_record(self, record: IdempotencyRecord) -> None:
        """Save or update idempotency record."""
        with self.db_manager.get_connection() as conn:
            # Try to insert first
            try:
                conn.execute(
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
                conn.execute(
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

    def update_state(self, idempotency_key: str, state: TaskState, result_data: str | None = None) -> None:
        """Update the state of an idempotency record."""
        with self.db_manager.get_connection() as conn:
            if result_data is not None:
                conn.execute(
                    """
                    UPDATE taskiq_idempotency_records
                    SET state = %s, updated_at = %s, result_data = %s
                    WHERE idempotency_key = %s
                """,
                    (state.value, datetime.now(UTC), result_data, idempotency_key),
                )
            else:
                conn.execute(
                    """
                    UPDATE taskiq_idempotency_records
                    SET state = %s, updated_at = %s
                    WHERE idempotency_key = %s
                """,
                    (state.value, datetime.now(UTC), idempotency_key),
                )
            conn.commit()

    def is_completed(self, idempotency_key: str) -> bool:
        """Check if a task is already completed."""
        record = self.get_record(idempotency_key)
        return record is not None and record.state == TaskState.COMPLETED


# Global instance - lazy initialization
_idempotency_storage: IdempotencyStorage | None = None


def get_idempotency_storage() -> IdempotencyStorage:
    """Get the global idempotency storage instance."""
    global _idempotency_storage
    if _idempotency_storage is None:
        _idempotency_storage = IdempotencyStorage()
    return _idempotency_storage
