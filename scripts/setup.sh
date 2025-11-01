#!/usr/bin/env bash
set -euo pipefail

# Setup script for Dagster TaskIQ LocalStack demo

log() {
    echo "[setup] $*"
}

check_dependencies() {
    log "Checking dependencies..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log "ERROR: Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log "ERROR: Docker Compose is not installed"
        exit 1
    fi
    
    # Check uv (required for dependency management)
    if ! command -v uv &> /dev/null; then
        log "ERROR: uv is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    
    # Check Pulumi (required for infrastructure)
    if ! command -v pulumi &> /dev/null; then
        log "ERROR: Pulumi is not installed. Install with: curl -fsSL https://get.pulumi.com | sh"
        exit 1
    fi
    
    log "All dependencies are available"
}

setup_environment() {
    log "Setting up environment..."
    
    # Copy environment file if it doesn't exist
    if [ ! -f .env ]; then
        cp .env.example .env
        log "Created .env file from .env.example"
    fi
    
    # Create LocalStack data directory
    mkdir -p localstack/data
    
    log "Environment setup complete"
}

install_app_dependencies() {
    log "Installing application dependencies..."
    
    cd app
    uv sync
    cd ..
    
    log "Application dependencies installed"
}

install_infra_dependencies() {
    log "Installing infrastructure dependencies..."
    
    cd deploy
    uv sync
    cd ..
    
    log "Infrastructure dependencies installed"
}

build_docker_images() {
    log "Building Docker images..."
    
    # Build the main application image
    docker build -t dagster-taskiq:latest -f app/Dockerfile app/
    
    log "Docker images built successfully"
}

start_localstack() {
    log "Starting LocalStack..."
    
    # Start LocalStack and PostgreSQL
    docker-compose up -d localstack postgres
    
    # Wait for LocalStack to be ready
    log "Waiting for LocalStack to be ready..."
    timeout=60
    while [ $timeout -gt 0 ]; do
        if curl -f http://localhost:4566/_localstack/health >/dev/null 2>&1; then
            log "LocalStack is ready"
            break
        fi
        sleep 2
        ((timeout-=2))
    done
    
    if [ $timeout -le 0 ]; then
        log "ERROR: LocalStack failed to start within 60 seconds"
        exit 1
    fi
    
    log "LocalStack started successfully"
}

deploy_infrastructure() {
    log "Deploying infrastructure with Pulumi..."
    
    cd deploy
    
    # Initialize Pulumi stack if it doesn't exist
    if ! pulumi stack ls | grep -q "dev"; then
        pulumi stack init dev
    fi
    
    # Set configuration
    pulumi config set aws:region us-east-1
    pulumi config set endpoint http://localhost:4566
    pulumi config set accessKey test
    pulumi config set secretKey test
    pulumi config set environment dev
    
    # Deploy infrastructure
    pulumi up --yes
    
    cd ..
    
    log "Infrastructure deployed successfully"
}

main() {
    log "Starting setup for Dagster TaskIQ LocalStack demo"
    
    check_dependencies
    setup_environment
    install_app_dependencies
    install_infra_dependencies
    build_docker_images
    start_localstack
    deploy_infrastructure
    
    log "Setup complete!"
    log ""
    log "Next steps:"
    log "1. Run 'docker-compose up -d' to start all services"
    log "2. Access Dagster UI at http://localhost:3000"
    log "3. Check LocalStack health at http://localhost:4566/_localstack/health"
}

main "$@"