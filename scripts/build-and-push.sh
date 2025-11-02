#!/usr/bin/env bash
# Build and push Docker image to LocalStack ECR using Docker Bake
#
# This script builds the application Docker image using Docker Bake and pushes it
# to LocalStack ECR using the awslocal CLI wrapper.
#
# Prerequisites:
# - LocalStack running (docker compose up localstack)
# - awslocal installed (mise use pipx:awscli-local)
# - ECR repository created by Pulumi
#
# Usage:
#   ./scripts/build-and-push.sh

set -euo pipefail

# Configuration
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-dagster-taskiq-demo}"
ENVIRONMENT="${ENVIRONMENT:-local}"
REPO_NAME="${PROJECT_NAME}-${ENVIRONMENT}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
LOCALSTACK_ENDPOINT="${LOCALSTACK_ENDPOINT:-http://localhost:4566}"

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🔨 Building Docker image with Docker Bake..."
echo "  Project: ${PROJECT_NAME}"
echo "  Environment: ${ENVIRONMENT}"
echo "  Tag: ${IMAGE_TAG}"

# Build the Docker image using Bake
cd "${PROJECT_ROOT}"
docker buildx bake \
  --set "*.platform=linux/amd64" \
  --set "app.tags=${REPO_NAME}:${IMAGE_TAG}" \
  app

echo "✅ Image built successfully: ${REPO_NAME}:${IMAGE_TAG}"

# Get the ECR repository URI from LocalStack
echo "🔍 Getting ECR repository URI..."
REPO_URI=$(awslocal ecr describe-repositories \
  --region "${REGION}" \
  --repository-names "${REPO_NAME}" \
  --query 'repositories[0].repositoryUri' \
  --output text 2>/dev/null || echo "")

if [ -z "${REPO_URI}" ]; then
  echo "❌ Error: ECR repository '${REPO_NAME}' not found in LocalStack"
  echo "   Make sure you've run Pulumi to create the repository first:"
  echo "   cd deploy && uv run pulumi up --yes --stack local"
  exit 1
fi

echo "  Repository URI: ${REPO_URI}"

# Tag the image for ECR
FULL_IMAGE_URI="${REPO_URI}:${IMAGE_TAG}"
echo "🏷️  Tagging image for ECR: ${FULL_IMAGE_URI}"
docker tag "${REPO_NAME}:${IMAGE_TAG}" "${FULL_IMAGE_URI}"

# Login to ECR (LocalStack doesn't validate credentials, but login is still required)
echo "🔐 Logging into LocalStack ECR..."
awslocal ecr get-login-password --region "${REGION}" | \
  docker login \
    --username AWS \
    --password-stdin \
    "${REPO_URI%%/*}"

# Push the image to LocalStack ECR
echo "⬆️  Pushing image to LocalStack ECR..."
docker push "${FULL_IMAGE_URI}"

echo "✅ Successfully pushed ${FULL_IMAGE_URI}"
echo ""
echo "Next steps:"
echo "  1. Verify image in LocalStack:"
echo "     awslocal ecr list-images --repository-name ${REPO_NAME}"
echo "  2. Deploy infrastructure with Pulumi (if not done yet):"
echo "     cd deploy && uv run pulumi up --yes --stack local"
