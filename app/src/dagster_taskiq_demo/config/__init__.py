"""Configuration package for Dagster TaskIQ LocalStack demo."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .settings import Settings, settings

if TYPE_CHECKING:  # pragma: no cover - typing helpers only
    from .dagster import DagsterPostgreSQLConfig, create_dagster_yaml_file, get_dagster_instance_config
    from .database import (
        DatabaseConnectionManager,
        create_dagster_instance_with_retry,
        get_database_manager,
        wait_for_database_ready,
    )
    from .metrics import MetricsCollector, get_metrics_collector

__all__ = [
    "DagsterPostgreSQLConfig",
    "DatabaseConnectionManager",
    "MetricsCollector",
    "Settings",
    "create_dagster_instance_with_retry",
    "create_dagster_yaml_file",
    "get_dagster_instance_config",
    "get_database_manager",
    "get_metrics_collector",
    "settings",
    "wait_for_database_ready",
]


_LAZY_IMPORTS = {
    "DagsterPostgreSQLConfig": ("dagster", "DagsterPostgreSQLConfig"),
    "create_dagster_yaml_file": ("dagster", "create_dagster_yaml_file"),
    "get_dagster_instance_config": ("dagster", "get_dagster_instance_config"),
    "DatabaseConnectionManager": ("database", "DatabaseConnectionManager"),
    "create_dagster_instance_with_retry": ("database", "create_dagster_instance_with_retry"),
    "get_database_manager": ("database", "get_database_manager"),
    "wait_for_database_ready": ("database", "wait_for_database_ready"),
    "MetricsCollector": ("metrics", "MetricsCollector"),
    "get_metrics_collector": ("metrics", "get_metrics_collector"),
}


def __getattr__(name: str) -> Any:
    """Dynamically import configuration helpers on demand.

    Returns:
        Attribute resolved from the lazily imported module.

    Raises:
        AttributeError: If the requested attribute is unknown.
    """
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        module = import_module(f"{__name__}.{module_name}")
        return getattr(module, attr_name)
    message = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(message)
