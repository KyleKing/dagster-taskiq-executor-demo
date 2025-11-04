"""Main entry point for the Dagster TaskIQ LocalStack demo application."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import structlog
from dagster import DagsterInstance

from .config import (
    create_dagster_instance_with_retry,
    get_database_manager,
    settings,
    wait_for_database_ready,
)
from .dagster_jobs import defs

logger = structlog.get_logger(__name__)


def setup_logging() -> None:
    """Configure structured logging for the application."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def ensure_dagster_home() -> None:
    """Ensure DAGSTER_HOME directory exists and dagster.yaml is present."""
    import importlib.resources

    dagster_home = Path(settings.dagster_home)
    dagster_home.mkdir(parents=True, exist_ok=True)

    dagster_yaml_path = dagster_home / "dagster.yaml"
    if not dagster_yaml_path.exists():
        logger.info("copying_dagster_yaml", path=str(dagster_yaml_path))
        # Copy the static dagster.yaml from package to DAGSTER_HOME
        package = "dagster_taskiq_demo.config"
        template_path = importlib.resources.files(package) / "dagster.yaml"
        template_content = template_path.read_text(encoding="utf-8")
        dagster_yaml_path.write_text(template_content, encoding="utf-8")
        logger.info("dagster_yaml_copied", path=str(dagster_yaml_path))
    else:
        logger.info("dagster_yaml_exists", path=str(dagster_yaml_path))


def initialize_database() -> None:
    """Initialize the database and wait for it to be ready."""
    logger.info("initializing_database")

    if not wait_for_database_ready(timeout=60):
        logger.error("database_initialization_failed")
        sys.exit(1)

    # Initialize database schema
    db_manager = get_database_manager()
    db_manager.initialize_database()

    logger.info("database_initialization_complete")


def create_dagster_instance() -> DagsterInstance:
    """Create and return a Dagster instance with retry logic.

    Returns:
        Configured Dagster instance ready for use.
    """
    logger.info("creating_dagster_instance")

    try:
        instance = create_dagster_instance_with_retry()
    except Exception as exc:
        logger.exception("dagster_instance_creation_failed", error=str(exc))
        sys.exit(1)
    else:
        logger.info("dagster_instance_created")
        return instance


async def main() -> None:
    """Main application entry point."""
    setup_logging()
    logger.info("application_starting", settings=settings.model_dump())

    # Ensure DAGSTER_HOME is set up
    ensure_dagster_home()

    # Initialize database
    initialize_database()

    # Create Dagster instance
    instance = create_dagster_instance()

    # Verify repository can be loaded
    try:
        # TODO: is this really necessary? If so, why are these attributes None?
        job_names = [job.name for job in defs.jobs or []]
        schedule_names = [schedule.name for schedule in defs.schedules or []]
        logger.info("repository_loaded", jobs=job_names, schedules=schedule_names)
    except Exception as exc:
        logger.exception("repository_load_failed", error=str(exc))
        sys.exit(1)

    logger.info("application_ready")

    # Keep the application running
    try:
        while True:
            await asyncio.sleep(60)  # Check every minute
            logger.debug("application_heartbeat")
    except KeyboardInterrupt:
        logger.info("application_shutdown_requested")
    finally:
        if instance:  # type: ignore[truthy-bool]
            instance.dispose()
        logger.info("application_shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())
