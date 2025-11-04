"""Dagster configuration helpers for PostgreSQL-backed storage."""

from __future__ import annotations

import pathlib
import time
from typing import Any

import structlog
from dagster_postgres import DagsterPostgresStorage

from .exceptions import DagsterDatabaseConnectionError
from .settings import settings

logger = structlog.get_logger(__name__)


class DagsterPostgreSQLConfig:
    """Configuration helpers for Dagster PostgreSQL storage backend."""

    @staticmethod
    def get_postgres_storage_config() -> dict[str, Any]:
        """Get PostgreSQL storage configuration for Dagster.

        Returns:
            Mapping compatible with Dagster's PostgreSQL storage configuration.
        """
        return {
            "postgres_url": settings.dagster_postgres_url,
            "should_autocreate_tables": True,
        }

    @staticmethod
    def get_run_storage_config() -> dict[str, Any]:
        """Get run storage configuration block.

        Returns:
            Run storage configuration block for Dagster YAML.
        """
        return {
            "module": "dagster_postgres.run_storage",
            "class": "DagsterPostgresRunStorage",
            "config": DagsterPostgreSQLConfig.get_postgres_storage_config(),
        }

    @staticmethod
    def get_event_log_storage_config() -> dict[str, Any]:
        """Get event log storage configuration block.

        Returns:
            Event log storage configuration block for Dagster YAML.
        """
        return {
            "module": "dagster_postgres.event_log",
            "class": "DagsterPostgresEventLogStorage",
            "config": DagsterPostgreSQLConfig.get_postgres_storage_config(),
        }

    @staticmethod
    def get_schedule_storage_config() -> dict[str, Any]:
        """Get schedule storage configuration block.

        Returns:
            Schedule storage configuration block for Dagster YAML.
        """
        return {
            "module": "dagster_postgres.schedule_storage",
            "class": "DagsterPostgresScheduleStorage",
            "config": DagsterPostgreSQLConfig.get_postgres_storage_config(),
        }

    @staticmethod
    def get_compute_log_storage_config() -> dict[str, Any]:
        """Get compute log storage configuration block.

        Returns:
            Compute log storage configuration block for Dagster YAML.
        """
        return {
            "module": "dagster._core.storage.noop_compute_log_manager",
            "class": "NoOpComputeLogManager",
        }

    @classmethod
    def get_dagster_yaml_config(cls) -> dict[str, Any]:
        """Build the complete Dagster YAML configuration.

        Returns:
            Full Dagster configuration dictionary for YAML serialization.
        """
        return {
            "storage": {
                "postgres": {
                    "postgres_url": settings.dagster_postgres_url,
                    "should_autocreate_tables": True,
                }
            },
            "run_coordinator": {
                "module": "dagster._core.run_coordinator",
                "class": "DefaultRunCoordinator",
            },
            "run_launcher": {
                "module": "dagster._core.launcher",
                "class": "DefaultRunLauncher",
            },
            "compute_logs": cls.get_compute_log_storage_config(),
        }


class RetryablePostgresStorage:
    """PostgreSQL storage helper with connection retry logic."""

    def __init__(
        self,
        postgres_url: str,
        *,
        should_autocreate_tables: bool = True,
        max_retries: int = 5,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize retryable PostgreSQL storage.

        Args:
            postgres_url: PostgreSQL connection URL
            should_autocreate_tables: Whether to auto-create tables
            max_retries: Maximum number of connection retries
            retry_delay: Delay between retries in seconds
        """
        self._postgres_url = postgres_url
        self._should_autocreate_tables = should_autocreate_tables
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    def create_storage(self) -> DagsterPostgresStorage:
        """Create PostgreSQL storage with retry logic.

        Returns:
            Dagster PostgreSQL storage instance.

        Raises:
            DagsterDatabaseConnectionError: If storage creation fails after retries.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                logger.debug("dagster_storage_attempt", attempt=attempt + 1)
                return DagsterPostgresStorage(
                    postgres_url=self._postgres_url,
                    should_autocreate_tables=self._should_autocreate_tables,
                )
            except Exception as exc:  # pragma: no cover - depends on external failure modes
                last_error = exc
                if attempt < self._max_retries - 1:
                    sleep_for = self._retry_delay * (2**attempt)
                    logger.warning(
                        "dagster_storage_retry_pending",
                        attempt=attempt + 1,
                        delay_seconds=sleep_for,
                        error=str(exc),
                    )
                    time.sleep(sleep_for)
                    continue
                break

        msg = f"Failed to connect to PostgreSQL after {self._max_retries} attempts. Last error: {last_error}"
        raise DagsterDatabaseConnectionError(msg) from last_error


def get_dagster_instance_config() -> dict[str, Any]:
    """Get Dagster instance configuration for programmatic setup.

    Returns:
        Dagster instance configuration dictionary.
    """
    return {
        "storage": {
            "postgres": {
                "postgres_url": settings.dagster_postgres_url,
                "should_autocreate_tables": True,
            }
        },
        "run_coordinator": {
            "module": "dagster._core.run_coordinator",
            "class": "DefaultRunCoordinator",
        },
        "run_launcher": {
            "module": "dagster._core.launcher",
            "class": "DefaultRunLauncher",
        },
        "compute_logs": {
            "module": "dagster._core.storage.noop_compute_log_manager",
            "class": "NoOpComputeLogManager",
        },
    }
