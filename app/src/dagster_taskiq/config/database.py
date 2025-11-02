"""Database connection management for the Dagster TaskIQ demo."""

from __future__ import annotations

import asyncio
import concurrent.futures
import time
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

import structlog
from dagster import DagsterInstance
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from .exceptions import DagsterDatabaseConnectionError
from .settings import settings

logger = structlog.get_logger(__name__)


class DatabaseConnectionManager:
    """Manage synchronous and asynchronous database connections with retries."""

    def __init__(
        self,
        postgres_url: str | None = None,
        max_retries: int = 5,
        retry_delay: float = 1.0,
        connection_timeout: int = 30,
    ) -> None:
        """Initialize database connection manager.

        Args:
            postgres_url: PostgreSQL connection URL (defaults to settings)
            max_retries: Maximum number of connection retries
            retry_delay: Base delay between retries in seconds
            connection_timeout: Connection timeout in seconds
        """
        self.postgres_url = postgres_url or settings.postgres_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connection_timeout = connection_timeout
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        """Get SQLAlchemy engine with lazy initialization."""
        if self._engine is None:
            self._engine = create_engine(
                self.postgres_url,
                connect_args={"connect_timeout": self.connection_timeout},
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._engine

    def test_connection(self) -> bool:
        """Test database connectivity.

        Returns:
            True if the database connection succeeds, otherwise False.
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # pragma: no cover - depends on external failure modes
            logger.warning("database_connection_test_failed", error=str(exc))
            return False
        return True

    def wait_for_database(self, timeout: int = 60) -> bool:
        """Wait for database to become available.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if database becomes available, False if timeout
        """
        start_time = time.time()
        attempt = 0

        while time.time() - start_time < timeout:
            attempt += 1
            logger.info("database_connection_attempt", attempt=attempt)

            if self.test_connection():
                logger.info("database_connection_successful")
                return True

            if attempt < self.max_retries:
                delay = min(self.retry_delay * (2 ** (attempt - 1)), 30)
                logger.info("database_connection_retry_wait", delay=delay)
                time.sleep(delay)
            else:
                logger.warning("database_max_retries_reached")
                time.sleep(5)

        logger.error("database_connection_timeout", timeout=timeout)
        return False

    @contextmanager
    def get_connection(self) -> Generator[Any]:
        """Get database connection with automatic retry and cleanup.

        Yields:
            Database connection

        Raises:
            DagsterDatabaseConnectionError: If connection fails after all retries
        """
        last_error: OperationalError | None = None

        for attempt in range(self.max_retries):
            try:
                with self.engine.connect() as conn:
                    yield conn
                    return
            except OperationalError as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        "database_connection_failed",
                        attempt=attempt + 1,
                        delay_seconds=delay,
                        error=str(exc),
                    )
                    time.sleep(delay)
                    continue
                break
            except Exception as exc:  # pragma: no cover - unexpected failure surfaces debugging info
                logger.exception("unexpected_database_error", error=str(exc))
                raise

        msg = f"Failed to connect to database after {self.max_retries} attempts. Last error: {last_error}"
        raise DagsterDatabaseConnectionError(msg) from last_error

    @asynccontextmanager
    async def get_async_connection(self) -> AsyncGenerator[Any]:
        """Get async database connection with retry logic.

        Note: This is a placeholder for async operations.
        For now, it wraps the sync connection in an async context.

        Yields:
            Active database connection wrapped for async usage.
        """
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self._get_sync_connection_context)
            try:
                conn = await asyncio.get_event_loop().run_in_executor(None, future.result)
                yield conn
            finally:
                future.cancel()

    def _get_sync_connection_context(self) -> Any:
        """Helper method for async connection management.

        Returns:
            Database connection from the sync context manager.
        """
        with self.get_connection() as conn:
            return conn

    def create_dagster_instance(self) -> DagsterInstance:
        """Create Dagster instance configured via dagster.yaml.

        Returns:
            Configured Dagster instance.

        Raises:
            DagsterDatabaseConnectionError: If instance creation fails.
        """
        if not self.wait_for_database():
            raise DagsterDatabaseConnectionError("Database is not available")

        try:
            return DagsterInstance.get()
        except Exception as exc:  # pragma: no cover - depends on external Dagster behavior
            msg = f"Failed to bootstrap Dagster instance: {exc}"
            raise DagsterDatabaseConnectionError(msg) from exc

    def initialize_database(self) -> None:
        """Initialize database schema and tables."""
        logger.info("database_schema_initializing")

        if not self.wait_for_database():
            raise DagsterDatabaseConnectionError("Cannot initialize database - connection failed")

        try:
            instance = self.create_dagster_instance()
            instance.dispose()
            with self.get_connection() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM runs"))
                logger.info("database_ready", run_count=result.scalar())
        except Exception as exc:  # pragma: no cover - depends on external DB state
            logger.exception("database_initialization_failed", error=str(exc))
            raise DagsterDatabaseConnectionError("Database initialization failed") from exc


db_manager = DatabaseConnectionManager()


def get_database_manager() -> DatabaseConnectionManager:
    """Get the global database manager instance.

    Returns:
        Shared `DatabaseConnectionManager` instance.
    """
    return db_manager


def create_dagster_instance_with_retry() -> DagsterInstance:
    """Create Dagster instance with connection retry logic.

    Returns:
        Fully configured Dagster instance.
    """
    return db_manager.create_dagster_instance()


def wait_for_database_ready(timeout: int = 60) -> bool:
    """Wait for database to become ready.

    Args:
        timeout: Maximum time to wait in seconds

    Returns:
        True if database is ready, False if timeout
    """
    return db_manager.wait_for_database(timeout)
