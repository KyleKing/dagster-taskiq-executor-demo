# Modifications copyright (c) 2024 dagster-taskiq contributors

"""CLI entrypoint for the TaskIQ worker."""

import argparse
import logging
import sys

from .worker import TaskIQWorker


def main() -> None:
    """Run the TaskIQ worker."""
    parser = argparse.ArgumentParser(description="TaskIQ worker for Dagster")
    parser.add_argument("--queue-url", required=True, help="SQS queue URL")
    parser.add_argument("--aws-endpoint-url", help="AWS endpoint URL (for LocalStack)")
    parser.add_argument("--aws-region", default="us-east-1", help="AWS region")
    parser.add_argument("--aws-access-key-id", help="AWS access key ID")
    parser.add_argument("--aws-secret-access-key", help="AWS secret access key")
    parser.add_argument("--visibility-timeout", type=int, default=300, help="SQS visibility timeout")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting TaskIQ worker")

    try:
        # Create and run worker
        worker = TaskIQWorker(
            queue_url=args.queue_url,
            aws_endpoint_url=args.aws_endpoint_url,
            aws_region=args.aws_region,
            aws_access_key_id=args.aws_access_key_id,
            aws_secret_access_key=args.aws_secret_access_key,
            visibility_timeout=args.visibility_timeout,
        )
        import asyncio
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.exception("Worker failed with error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()