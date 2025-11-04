#!/bin/bash
# Script to run TaskIQ dashboard with dev dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT/dagster-taskiq"

echo "Starting TaskIQ Dashboard..."
echo "Make sure dev dependencies are installed: uv sync --group dev"
echo "Dashboard will be available at: http://localhost:8080"
echo "Press Ctrl+C to stop"
echo ""

# Run with dev dependencies
uv run --group dev dagster-taskiq worker dashboard "$@"
