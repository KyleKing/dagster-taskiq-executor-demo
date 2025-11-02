"""Dagster jobs and repository definitions."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    FastOpConfig = Any
    SlowOpConfig = Any
    aggregation_op = Any
    create_development_repository = Any
    create_production_repository = Any
    create_repository = Any
    create_testing_repository = Any
    data_processing_op = Any
    fast_async_op = Any
    fast_job = Any
    get_all_schedules = Any
    get_testing_schedules = Any
    mixed_job = Any
    parallel_fast_job = Any
    repository = Any
    sequential_slow_job = Any
    slow_async_op = Any
    slow_job = Any

__all__ = [
    "FastOpConfig",
    "SlowOpConfig",
    "aggregation_op",
    "create_development_repository",
    "create_production_repository",
    "create_repository",
    "create_testing_repository",
    "data_processing_op",
    "fast_async_op",
    "fast_job",
    "get_all_schedules",
    "get_testing_schedules",
    "mixed_job",
    "parallel_fast_job",
    "repository",
    "sequential_slow_job",
    "slow_async_op",
    "slow_job",
]

_LAZY_IMPORTS = {
    "FastOpConfig": ("ops", "FastOpConfig"),
    "SlowOpConfig": ("ops", "SlowOpConfig"),
    "aggregation_op": ("ops", "aggregation_op"),
    "create_development_repository": ("repository", "create_development_repository"),
    "create_production_repository": ("repository", "create_production_repository"),
    "create_repository": ("repository", "create_repository"),
    "create_testing_repository": ("repository", "create_testing_repository"),
    "data_processing_op": ("ops", "data_processing_op"),
    "fast_async_op": ("ops", "fast_async_op"),
    "fast_job": ("jobs", "fast_job"),
    "get_all_schedules": ("schedules", "get_all_schedules"),
    "get_testing_schedules": ("schedules", "get_testing_schedules"),
    "mixed_job": ("jobs", "mixed_job"),
    "parallel_fast_job": ("jobs", "parallel_fast_job"),
    "repository": ("repository", "repository"),
    "sequential_slow_job": ("jobs", "sequential_slow_job"),
    "slow_async_op": ("ops", "slow_async_op"),
    "slow_job": ("jobs", "slow_job"),
}


def __getattr__(name: str) -> Any:
    """Lazily import Dagster job helpers to minimise import-time side effects.

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
