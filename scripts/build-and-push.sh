#!/usr/bin/env bash
# Build and push Docker image to AWS ECR

set -euo pipefail

# Configuration
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
REPO_NAME="${PROJECT_NAME:-dagster-taskiq-demo}-${ENVIRONMENT}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
BAKE_TARGET="${BAKE_TARGET:-dagster-taskiq-demo}"
LOCAL_IMAGE="${LOCAL_IMAGE:-${BAKE_TARGET}}"

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "Building Docker image target '${BAKE_TARGET}'..."
docker buildx bake "${BAKE_TARGET}"

echo "Getting ECR repository URI..."
REPO_URI=$(aws ecr describe-repositories \
  --region "${REGION}" \
  --repository-names "${REPO_NAME}" \
  --query 'repositories[0].repositoryUri' \
  --output text 2>/dev/null) || {
  echo "ECR repository '${REPO_NAME}' not found."
  echo "Run: cd deploy && uv run pulumi up --stack ${ENVIRONMENT}"
  exit 1
}

FULL_IMAGE_URI="${REPO_URI}:${IMAGE_TAG}"
echo "Tagging and pushing to ECR..."
docker tag "${LOCAL_IMAGE}:latest" "${FULL_IMAGE_URI}"
aws ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${REPO_URI%%/*}"
docker push "${FULL_IMAGE_URI}"

echo "Pushed ${FULL_IMAGE_URI}"
echo "Verify: aws ecr list-images --repository-name ${REPO_NAME} --region ${REGION}"
