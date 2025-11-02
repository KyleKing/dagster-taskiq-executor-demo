"""CLI entrypoint for the auto-scaler service."""

import logging
import signal
import sys
from typing import Any

from dagster_taskiq_demo.auto_scaler import AutoScalerService, settings


def main() -> None:
    """Run the auto-scaler service."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting auto-scaler service")

    # Create service instance
    auto_scaler_service = AutoScalerService(settings)

    # Handle shutdown signals
    def signal_handler(signum: int, frame: Any) -> None:
        logger.info("Received signal %s, shutting down", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Run the service
        auto_scaler_service.run_service()
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.exception("Service failed with error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()