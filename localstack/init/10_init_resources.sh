#!/usr/bin/env bash
set -euo pipefail

# Configuration
PROJECT_NAME="dagster-taskiq-demo"
ENVIRONMENT="dev"
QUEUE_NAME="${PROJECT_NAME}-taskiq-${ENVIRONMENT}.fifo"
DLQ_NAME="${PROJECT_NAME}-taskiq-dlq-${ENVIRONMENT}.fifo"
CLUSTER_NAME="${PROJECT_NAME}-${ENVIRONMENT}"

log() {
    echo "[localstack:init] $*"
}

wait_for_service() {
    local service=$1
    local max_attempts=30
    local attempt=1
    
    log "Waiting for $service to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if awslocal $service help >/dev/null 2>&1; then
            log "$service is ready"
            return 0
        fi
        log "Attempt $attempt/$max_attempts: $service not ready yet"
        sleep 2
        ((attempt++))
    done
    
    log "ERROR: $service failed to become ready after $max_attempts attempts"
    return 1
}

create_fifo_queue() {
    local queue_name=$1
    local description=$2
    
    if awslocal sqs get-queue-url --queue-name "${queue_name}" >/dev/null 2>&1; then
        log "SQS FIFO queue '${queue_name}' already exists"
    else
        log "Creating SQS FIFO queue '${queue_name}' (${description})"
        awslocal sqs create-queue \
            --queue-name "${queue_name}" \
            --attributes '{
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
                "DeduplicationScope": "messageGroup",
                "FifoThroughputLimit": "perMessageGroupId",
                "VisibilityTimeout": "300",
                "MessageRetentionPeriod": "1209600"
            }'
    fi
}

create_cluster() {
    if awslocal ecs describe-clusters --clusters "${CLUSTER_NAME}" --query "clusters[0].status" --output text 2>/dev/null | grep -q "ACTIVE"; then
        log "ECS cluster '${CLUSTER_NAME}' already exists and is active"
    else
        log "Creating ECS cluster '${CLUSTER_NAME}'"
        awslocal ecs create-cluster --cluster-name "${CLUSTER_NAME}"
    fi
}

create_log_groups() {
    local log_groups=(
        "/aws/ecs/dagster-daemon"
        "/aws/ecs/dagster-webserver"
        "/aws/ecs/taskiq-worker"
        "/aws/ecs/auto-scaler"
        "/aws/ecs/load-simulator"
    )
    
    for log_group in "${log_groups[@]}"; do
        if awslocal logs describe-log-groups --log-group-name-prefix "${log_group}" --query "logGroups[?logGroupName=='${log_group}']" --output text | grep -q "${log_group}"; then
            log "CloudWatch log group '${log_group}' already exists"
        else
            log "Creating CloudWatch log group '${log_group}'"
            awslocal logs create-log-group --log-group-name "${log_group}"
        fi
    done
}

wait_for_rds() {
    local db_identifier="${PROJECT_NAME}-rds-${ENVIRONMENT}"
    local max_attempts=60
    local attempt=1
    
    log "Waiting for RDS instance '${db_identifier}' to be available..."
    while [ $attempt -le $max_attempts ]; do
        local status=$(awslocal rds describe-db-instances --db-instance-identifier "${db_identifier}" --query "DBInstances[0].DBInstanceStatus" --output text 2>/dev/null || echo "not-found")
        
        if [ "$status" = "available" ]; then
            log "RDS instance '${db_identifier}' is available"
            return 0
        elif [ "$status" = "not-found" ]; then
            log "Attempt $attempt/$max_attempts: RDS instance not found yet"
        else
            log "Attempt $attempt/$max_attempts: RDS instance status is '$status'"
        fi
        
        sleep 5
        ((attempt++))
    done
    
    log "WARNING: RDS instance failed to become available after $max_attempts attempts"
    return 1
}

initialize_dagster_database() {
    local db_identifier="${PROJECT_NAME}-rds-${ENVIRONMENT}"
    
    # Get RDS endpoint
    local endpoint=$(awslocal rds describe-db-instances --db-instance-identifier "${db_identifier}" --query "DBInstances[0].Endpoint.Address" --output text 2>/dev/null || echo "")
    
    if [ -z "$endpoint" ]; then
        log "WARNING: Could not get RDS endpoint, skipping database initialization"
        return 1
    fi
    
    log "Initializing Dagster database schema on endpoint: ${endpoint}"
    
    # Note: In a real implementation, we would run Dagster's database migration commands here
    # For LocalStack demo, we'll let Dagster handle schema creation on first run
    log "Database initialization will be handled by Dagster daemon on first startup"
    
    return 0
}

log "Starting LocalStack initialization for Dagster TaskIQ demo"

# Wait for services to be ready
wait_for_service "sqs"
wait_for_service "ecs"
wait_for_service "logs"
wait_for_service "rds"

# Create resources
create_fifo_queue "${QUEUE_NAME}" "Main TaskIQ queue"
create_fifo_queue "${DLQ_NAME}" "Dead letter queue"
create_cluster
create_log_groups

# Wait for and initialize RDS (if available)
if wait_for_rds; then
    initialize_dagster_database
fi

log "LocalStack initialization complete"
log "Resources created:"
log "  - SQS FIFO Queue: ${QUEUE_NAME}"
log "  - SQS Dead Letter Queue: ${DLQ_NAME}"
log "  - ECS Cluster: ${CLUSTER_NAME}"
log "  - CloudWatch Log Groups: /aws/ecs/*"
