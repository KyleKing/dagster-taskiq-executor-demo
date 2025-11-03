from dagster_shared.libraries import DagsterLibraryRegistry

from dagster_taskiq.executor import taskiq_executor
from dagster_taskiq.version import __version__

DagsterLibraryRegistry.register("dagster-taskiq", __version__)

__all__ = ["taskiq_executor"]
