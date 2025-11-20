"""Dagster TaskIQ integration library.

This package provides a Taskiq-based executor and run launcher for Dagster,
enabling distributed task execution via AWS SQS.
"""

from dagster_shared.libraries import DagsterLibraryRegistry

from dagster_taskiq.executor import taskiq_executor
from dagster_taskiq.launcher import TaskiqRunLauncher

__verion__ = "0.0.0"

DagsterLibraryRegistry.register("dagster-taskiq", __version__)

__all__ = ["TaskiqRunLauncher", "taskiq_executor"]
