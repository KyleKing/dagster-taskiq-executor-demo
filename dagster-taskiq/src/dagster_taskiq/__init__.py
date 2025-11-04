"""Dagster TaskIQ integration library.

This package provides a Taskiq-based executor and run launcher for Dagster,
enabling distributed task execution via AWS SQS.
"""

from dagster_shared.libraries import DagsterLibraryRegistry

from dagster_taskiq.executor import taskiq_executor
from dagster_taskiq.launcher import TaskiqRunLauncher
from dagster_taskiq.version import __version__

DagsterLibraryRegistry.register("dagster-taskiq", __version__)

__all__ = ["TaskiqRunLauncher", "taskiq_executor"]
