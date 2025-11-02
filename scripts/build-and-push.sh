#!/usr/bin/env bash
# Build and push Docker image to LocalStack ECR

set -euo pipefail

# Configuration
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
REPO_NAME="${PROJECT_NAME:-dagster-taskiq-demo}-${ENVIRONMENT:-local}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "🔨 Building Docker image..."
docker buildx bake dagster-taskiq-demo

echo "🔍 Getting ECR repository URI..."
REPO_URI=$(awslocal ecr describe-repositories \
  --region "${REGION}" \
  --repository-names "${REPO_NAME}" \
  --query 'repositories[0].repositoryUri' \
  --output text) || {
  echo "❌ ECR repository '${REPO_NAME}' not found. Run: cd deploy && uv run pulumi up --yes --stack local"
  exit 1
}

FULL_IMAGE_URI="${REPO_URI}:${IMAGE_TAG}"
echo "🏷️  Tagging and pushing to ECR..."
docker tag "dagster-taskiq-demo:latest" "${FULL_IMAGE_URI}"
awslocal ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${REPO_URI%%/*}"
docker push "${FULL_IMAGE_URI}"

echo "✅ Pushed ${FULL_IMAGE_URI}"
echo "Verify: awslocal ecr list-images --repository-name ${REPO_NAME}"
