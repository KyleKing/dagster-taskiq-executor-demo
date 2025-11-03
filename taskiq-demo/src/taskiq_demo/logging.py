"""Structured logging helpers shared by the API and worker."""

from __future__ import annotations

import logging
from typing import Any

import structlog

from .config import get_settings

_CONFIGURED = False


def configure_logging(level: int | str | None = None) -> None:
    """Initialise standard logging and structlog configuration."""
    global _CONFIGURED
    if _CONFIGURED:
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
    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger."""
    configure_logging()
    return structlog.get_logger(name)


def _resolve_level(raw_level: Any) -> int:
    """Convert a string or logging level constant into an integer level."""
    if isinstance(raw_level, int):
        return raw_level
    level_value = logging.getLevelName(str(raw_level))
    if isinstance(level_value, int):
        return level_value
    return logging.INFO
