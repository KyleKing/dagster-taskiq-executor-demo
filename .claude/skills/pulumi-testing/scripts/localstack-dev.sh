#!/usr/bin/env bash
# Development workflow utilities for Pulumi + LocalStack
#
# This script provides common operations for managing the lifecycle
# mismatch between ephemeral LocalStack and persistent Pulumi state.

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# LocalStack configuration
LOCALSTACK_ENDPOINT="${LOCALSTACK_ENDPOINT:-http://localhost:4566}"
PULUMI_BACKEND="${PULUMI_BACKEND:-file://~/.pulumi}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_localstack() {
    if ! curl -s "${LOCALSTACK_ENDPOINT}/_localstack/health" > /dev/null 2>&1; then
        return 1
    fi
    return 0
}

check_pulumi_stack() {
    if ! pulumi stack --show-name > /dev/null 2>&1; then
        log_error "Not in a Pulumi project or no stack selected"
        return 1
    fi
    return 0
}

# Start LocalStack with Pulumi-friendly configuration
start_localstack() {
    log_info "Starting LocalStack..."

    if check_localstack; then
        log_warn "LocalStack already running"
        return 0
    fi

    # Start LocalStack with persistence
    docker run -d \
        --name localstack \
        -p 4566:4566 \
        -e SERVICES="s3,sqs,dynamodb,iam,sts,lambda,ecs,rds,ec2" \
        -e DEBUG=1 \
        -e PERSISTENCE=1 \
        -e DATA_DIR=/tmp/localstack/data \
        -v localstack-data:/tmp/localstack \
        localstack/localstack:latest

    log_info "Waiting for LocalStack to be ready..."
    for i in {1..30}; do
        if check_localstack; then
            log_info "LocalStack is ready"
            return 0
        fi
        sleep 2
    done

    log_error "LocalStack failed to start"
    return 1
}

# Stop LocalStack (keeps container for restart)
stop_localstack() {
    log_info "Stopping LocalStack..."
    docker stop localstack || true
    log_info "LocalStack stopped (use restart_localstack to resume)"
}

# Restart LocalStack (preserves state if PERSISTENCE=1)
restart_localstack() {
    log_info "Restarting LocalStack..."

    if docker ps -a | grep -q localstack; then
        docker start localstack
    else
        start_localstack
    fi

    log_info "Waiting for LocalStack to be ready..."
    for i in {1..30}; do
        if check_localstack; then
            log_info "LocalStack is ready"
            return 0
        fi
        sleep 2
    done

    log_error "LocalStack failed to restart"
    return 1
}

# Nuclear option: completely destroy LocalStack and its data
destroy_localstack() {
    log_warn "This will DESTROY LocalStack container and ALL data"
    read -p "Continue? [yes/no]: " -r
    if [[ ! $REPLY =~ ^yes$ ]]; then
        log_info "Aborted"
        return 0
    fi

    log_info "Destroying LocalStack..."
    docker rm -f localstack || true
    docker volume rm localstack-data || true
    log_info "LocalStack destroyed"
}

# Fresh start: destroy LocalStack, clear Pulumi state, redeploy
fresh_start() {
    log_warn "FRESH START: This will destroy LocalStack AND Pulumi state"
    read -p "Continue? [yes/no]: " -r
    if [[ ! $REPLY =~ ^yes$ ]]; then
        log_info "Aborted"
        return 0
    fi

    # Step 1: Try to destroy Pulumi resources (may fail)
    log_info "Step 1: Destroying Pulumi resources..."
    pulumi destroy --yes || log_warn "Destroy failed (expected if LocalStack was already down)"

    # Step 2: Destroy LocalStack
    log_info "Step 2: Destroying LocalStack..."
    docker rm -f localstack || true
    docker volume rm localstack-data || true

    # Step 3: Start fresh LocalStack
    log_info "Step 3: Starting fresh LocalStack..."
    start_localstack

    # Step 4: Redeploy infrastructure
    log_info "Step 4: Redeploying infrastructure..."
    pulumi up --yes

    log_info "Fresh start complete!"
}

# Sync Pulumi state with LocalStack reality
sync_state() {
    log_info "Syncing Pulumi state with LocalStack..."

    if ! check_localstack; then
        log_error "LocalStack is not running. Start it first with: $0 start"
        return 1
    fi

    if ! check_pulumi_stack; then
        return 1
    fi

    # Use pulumi refresh to sync state
    log_info "Running pulumi refresh..."
    if pulumi refresh --yes; then
        log_info "State synced successfully"
    else
        log_error "State sync failed"
        log_warn "You may need to run: $0 fresh-start"
        return 1
    fi
}

# Check if Pulumi state and LocalStack are in sync
check_sync() {
    log_info "Checking sync status..."

    if ! check_localstack; then
        log_error "LocalStack is not running"
        log_warn "Run: $0 start"
        return 1
    fi

    if ! check_pulumi_stack; then
        return 1
    fi

    # Run refresh in preview mode to see if there are changes
    log_info "Running pulumi refresh --preview-only..."
    if pulumi refresh --preview-only; then
        log_info "State appears to be in sync"
        return 0
    else
        log_warn "State may be diverged"
        log_warn "Run: $0 sync to fix"
        return 1
    fi
}

# Export Pulumi state as backup
backup_state() {
    local stack_name
    stack_name=$(pulumi stack --show-name)
    local backup_file="pulumi-state-${stack_name}-$(date +%Y%m%d-%H%M%S).json"

    log_info "Backing up Pulumi state to ${backup_file}..."
    pulumi stack export --file "${backup_file}"
    log_info "Backup saved to ${backup_file}"
}

# Restore Pulumi state from backup
restore_state() {
    local backup_file="${1:-}"

    if [[ -z "${backup_file}" ]]; then
        log_error "Usage: $0 restore <backup-file>"
        return 1
    fi

    if [[ ! -f "${backup_file}" ]]; then
        log_error "Backup file not found: ${backup_file}"
        return 1
    fi

    log_warn "This will REPLACE current Pulumi state"
    read -p "Continue? [yes/no]: " -r
    if [[ ! $REPLY =~ ^yes$ ]]; then
        log_info "Aborted"
        return 0
    fi

    log_info "Restoring state from ${backup_file}..."
    pulumi stack import --file "${backup_file}"
    log_info "State restored"
}

# Show status of LocalStack and Pulumi
status() {
    echo "=== LocalStack + Pulumi Status ==="
    echo

    # LocalStack status
    if check_localstack; then
        log_info "LocalStack: ${GREEN}RUNNING${NC}"
        echo "  Endpoint: ${LOCALSTACK_ENDPOINT}"

        # Show some LocalStack info
        echo "  Services:"
        curl -s "${LOCALSTACK_ENDPOINT}/_localstack/health" | jq -r '.services | to_entries[] | "    \(.key): \(.value)"' 2>/dev/null || echo "    (unable to fetch)"
    else
        log_warn "LocalStack: ${RED}NOT RUNNING${NC}"
        echo "  Run: $0 start"
    fi

    echo

    # Pulumi status
    if check_pulumi_stack; then
        local stack_name
        stack_name=$(pulumi stack --show-name)
        log_info "Pulumi Stack: ${GREEN}${stack_name}${NC}"

        # Count resources
        local resource_count
        resource_count=$(pulumi stack export | jq '.deployment.resources | length' 2>/dev/null || echo "unknown")
        echo "  Resources: ${resource_count}"

        # Show last update
        echo "  Last update: $(pulumi stack export | jq -r '.deployment.manifest.time' 2>/dev/null || echo 'unknown')"
    else
        log_warn "Pulumi: ${RED}NOT IN PROJECT${NC}"
    fi

    echo
}

# Show help
show_help() {
    cat << EOF
Usage: $0 <command>

Development workflow utilities for Pulumi + LocalStack

COMMANDS:
    start           Start LocalStack container
    stop            Stop LocalStack (preserves state)
    restart         Restart LocalStack
    destroy         Completely destroy LocalStack and data

    sync            Sync Pulumi state with LocalStack reality
    check           Check if Pulumi and LocalStack are in sync
    fresh-start     Nuclear option: destroy everything and redeploy

    backup          Backup current Pulumi state
    restore <file>  Restore Pulumi state from backup

    status          Show status of LocalStack and Pulumi

COMMON WORKFLOWS:
    # Initial setup
    $0 start
    pulumi up

    # After LocalStack container restart
    $0 restart
    $0 sync

    # When things are broken
    $0 check          # See what's wrong
    $0 sync           # Try to fix
    $0 fresh-start    # Nuclear option

    # Before making risky changes
    $0 backup
    pulumi up
    # If it breaks:
    $0 restore <backup-file>

ENVIRONMENT:
    LOCALSTACK_ENDPOINT     LocalStack endpoint (default: http://localhost:4566)
    PULUMI_BACKEND          Pulumi backend (default: file://~/.pulumi)

EOF
}

# Main command dispatcher
main() {
    local command="${1:-}"

    case "${command}" in
        start)
            start_localstack
            ;;
        stop)
            stop_localstack
            ;;
        restart)
            restart_localstack
            ;;
        destroy)
            destroy_localstack
            ;;
        sync)
            sync_state
            ;;
        check)
            check_sync
            ;;
        fresh-start)
            fresh_start
            ;;
        backup)
            backup_state
            ;;
        restore)
            restore_state "${2:-}"
            ;;
        status)
            status
            ;;
        help|--help|-h|"")
            show_help
            ;;
        *)
            log_error "Unknown command: ${command}"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
