"""Structured logging helpers shared by the API and worker."""

from __future__ import annotations

import logging
from typing import Any

import structlog

from .config import get_settings


def configure_logging(level: int | str | None = None) -> None:
    """Initialise standard logging and structlog configuration."""
    if hasattr(configure_logging, "_configured") and configure_logging._configured:  # type: ignore
        return

    settings = get_settings()
    configured_level = _resolve_level(level or settings.log_level_value)

    logging.basicConfig(
        level=configured_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", key="ts"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(configured_level),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    configure_logging._configured = True  # type: ignore


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger.

    Args:
        name: The logger name.

    Returns:
        A configured structlog logger.

    """
    configure_logging()
    return structlog.get_logger(name)


def _resolve_level(raw_level: Any) -> int:
    """Convert a string or logging level constant into an integer level.

    Args:
        raw_level: The raw log level value.

    Returns:
        The integer log level.

    """
    if isinstance(raw_level, int):
        return raw_level
    level_names = logging.getLevelNamesMapping()
    return level_names.get(str(raw_level), logging.INFO)
