"""Dagster TaskIQ LocalStack demo package."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .config import settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    defs = Any
    main = Any

__all__ = ["defs", "main", "settings"]

__version__ = "0.0.0"

_LAZY_IMPORTS = {
    "defs": ("dagster_jobs", "defs"),
    "main": ("main", "main"),
}


def __getattr__(name: str) -> Any:
    """Lazily import top-level helpers to keep lightweight imports.

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
