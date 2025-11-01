#!/usr/bin/env bash
set -euo pipefail

QUEUE_NAME="${LOCALSTACK_SQS_QUEUE_NAME:-demo-queue}"
CLUSTER_NAME="${LOCALSTACK_ECS_CLUSTER_NAME:-demo-cluster}"

log() {
    echo "[localstack:init] $*"
}

create_queue() {
    if awslocal sqs get-queue-url --queue-name "${QUEUE_NAME}" >/dev/null 2>&1; then
        log "SQS queue '${QUEUE_NAME}' already exists"
    else
        log "Creating SQS queue '${QUEUE_NAME}'"
        awslocal sqs create-queue --queue-name "${QUEUE_NAME}"
    fi
}

create_cluster() {
    if awslocal ecs describe-clusters --clusters "${CLUSTER_NAME}" --query "clusters[0].status" --output text >/dev/null 2>&1; then
        log "ECS cluster '${CLUSTER_NAME}' already exists"
    else
        log "Creating ECS cluster '${CLUSTER_NAME}'"
        awslocal ecs create-cluster --cluster-name "${CLUSTER_NAME}"
    fi
}

log "Initializing LocalStack resources"
create_queue
create_cluster
log "Initialization complete"
