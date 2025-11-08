"""Exactly-once verification tooling for load simulation.

NOTE: This verification was designed for the custom TaskIQ executor implementation
that used PostgreSQL idempotency storage. The current dagster-taskiq
implementation uses taskiq's result backend instead. This verification is not
compatible with the current executor.
"""

from typing import Any

from dagster_taskiq_demo.config.settings import Settings


class VerificationResult:
    """Result of exactly-once verification."""


class RunVerificationDetail:
    """Detailed verification for a single run."""


class StepVerificationDetail:
    """Verification detail for a single step."""


class ExactlyOnceVerifier:
    """Verifier for exactly-once execution semantics."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the verifier.

        Args:
            settings: Application settings
        """
        self.settings = settings

    def verify_idempotency_records(self, scenario_tag: str | None = None) -> VerificationResult:
        """Verify exactly-once execution by checking idempotency records.

        Args:
            scenario_tag: Optional tag to filter runs by scenario

        Returns:
            Verification results

        Raises:
            NotImplementedError: This verification is not compatible with the current executor
        """
        raise NotImplementedError(
            "This verification was designed for the custom TaskIQ executor implementation "
            "that used PostgreSQL idempotency storage. The current dagster-taskiq "
            "implementation uses taskiq's result backend instead and does not support this "
            "verification mechanism."
        )

    def export_report(self, result: VerificationResult, output_path: Any, output_format: str = "json") -> None:
        """Export verification results to file.

        Args:
            result: Verification results
            output_path: Path to output file
            output_format: Output format ('json' or 'csv')

        Raises:
            NotImplementedError: This verification is not compatible with the current executor
        """
        raise NotImplementedError(
            "This verification was designed for the custom TaskIQ executor implementation "
            "that used PostgreSQL idempotency storage. The current dagster-taskiq "
            "implementation uses taskiq's result backend instead and does not support this "
            "verification mechanism."
        )
