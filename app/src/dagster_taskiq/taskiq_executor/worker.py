"""CLI entrypoint for the TaskIQ worker."""

import logging
import signal
import sys
from typing import Any

from dagster_taskiq.taskiq_executor.app import taskiq_app


def main() -> None:
    """Run the TaskIQ worker."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting TaskIQ worker")

    # Handle shutdown signals
    def signal_handler(signum: int, frame: Any) -> None:
        logger.info("Received signal %s, shutting down", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Run the worker
        taskiq_app.run_worker()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.exception("Worker failed with error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
