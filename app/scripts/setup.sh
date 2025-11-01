#!/usr/bin/env bash
set -euo pipefail

# Setup script for Dagster TaskIQ LocalStack demo

log() {
    echo "[setup] $*"
}

check_dependencies() {
    log "Checking dependencies..."
    
    if ! command -v uv &> /dev/null; then
        log "ERROR: uv is not installed. Please install uv first."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log "ERROR: Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log "ERROR: Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    log "All dependencies are available"
}

setup_python_env() {
    log "Setting up Python environment..."
    cd "$(dirname "$0")/.."
    
    if [ ! -f ".env" ]; then
        log "Creating .env file from template..."
        cp ../.env.example .env
    fi
    
    log "Installing Python dependencies with uv..."
    uv sync
    
    log "Python environment setup complete"
}

setup_infrastructure() {
    log "Setting up infrastructure..."
    cd "$(dirname "$0")/../deploy"
    
    if [ ! -f "uv.lock" ]; then
        log "Installing Pulumi dependencies..."
        uv sync
    fi
    
    log "Infrastructure setup complete"
}

main() {
    log "Starting setup for Dagster TaskIQ LocalStack demo"
    
    check_dependencies
    setup_python_env
    setup_infrastructure
    
    log "Setup complete!"
    log ""
    log "Next steps:"
    log "1. Start LocalStack: docker-compose up -d"
    log "2. Deploy infrastructure: cd deploy && uv run pulumi up"
    log "3. Run Dagster: cd app && uv run dagster dev"
}

main "$@"