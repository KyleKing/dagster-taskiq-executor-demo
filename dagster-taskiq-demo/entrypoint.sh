#!/bin/bash
set -euo pipefail

# Initialize Dagster configuration
echo "Initializing Dagster configuration..."
python3 -c "
from dagster_taskiq_demo.config import create_dagster_yaml_file, settings
from pathlib import Path
import structlog

# Setup logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger(__name__)

# Ensure DAGSTER_HOME exists
dagster_home = Path(settings.dagster_home)
dagster_home.mkdir(parents=True, exist_ok=True)

# Create dagster.yaml if it doesn't exist
dagster_yaml_path = dagster_home / 'dagster.yaml'
if not dagster_yaml_path.exists():
    logger.info('creating_dagster_yaml', path=str(dagster_yaml_path))
    create_dagster_yaml_file(dagster_yaml_path)
    logger.info('dagster_yaml_created', path=str(dagster_yaml_path))
else:
    logger.info('dagster_yaml_exists', path=str(dagster_yaml_path))
"

echo "Dagster configuration initialized. Starting service..."

# Execute the command passed as arguments or default to daemon
exec "${@:-dagster-daemon run}"
