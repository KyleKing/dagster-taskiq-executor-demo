"""CLI helpers for running the TaskIQ demo services."""

from __future__ import annotations

import os

import uvicorn

from .config import get_settings
from .logging import configure_logging, get_logger
from .service import app
from .worker import main as run_worker


def run_api() -> None:
    """Run the FastAPI application with uvicorn."""
    settings = get_settings()
    configure_logging()
    host = os.environ.get("HOST", settings.api_host)
    port = int(os.environ.get("PORT", settings.api_port))
    logger = get_logger(__name__)
    logger.info("api.run", host=host, port=port)
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_config=None,
        log_level=settings.log_level.lower(),
    )


def run(role: str | None = None) -> None:
    """Dispatch to the API or worker based on role argument.

    Args:
        role: The role to run ('api' or 'worker'). Defaults to 'api'.

    Raises:
        SystemExit: If an unsupported role is provided.

    """
    role_name = (role or os.environ.get("SERVICE_ROLE", "api")).lower()
    if role_name == "api":
        run_api()
        return
    if role_name == "worker":
        run_worker()
        return
    msg = f"Unsupported SERVICE_ROLE '{role_name}'."
    raise SystemExit(msg)


if __name__ == "__main__":
    run()
