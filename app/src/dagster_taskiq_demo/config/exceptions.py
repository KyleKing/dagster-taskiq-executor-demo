"""Custom exception hierarchy for Dagster TaskIQ configuration."""


class DagsterConfigError(RuntimeError):
    """Base exception for Dagster TaskIQ configuration issues."""


class DagsterDatabaseConnectionError(DagsterConfigError):
    """Raised when database connectivity for Dagster cannot be established."""
