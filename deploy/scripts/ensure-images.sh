#!/usr/bin/env bash
# Ensure Docker images are built and available in ECR before Pulumi deployment

set -euo pipefail

# Configuration
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
PROJECT_NAME="${PROJECT_NAME:-dagster-taskiq-demo}"
ENVIRONMENT="${ENVIRONMENT:-local}"
REPO_NAME="${PROJECT_NAME}-${ENVIRONMENT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔍 Checking ECR repository '${REPO_NAME}'...${NC}"

# Check if repository exists
if ! awslocal ecr describe-repositories \
  --region "${REGION}" \
  --repository-names "${REPO_NAME}" \
  --query 'repositories[0].repositoryUri' \
  --output text >/dev/null 2>&1; then

  echo -e "${YELLOW}📦 ECR repository '${REPO_NAME}' not found. Creating it...${NC}"
  awslocal ecr create-repository \
    --region "${REGION}" \
    --repository-name "${REPO_NAME}" \
    --image-scanning-configuration scanOnPush=false \
    --image-tag-mutability MUTABLE >/dev/null

  echo -e "${GREEN}✅ Created ECR repository '${REPO_NAME}'${NC}"
else
  echo -e "${GREEN}✅ ECR repository '${REPO_NAME}' exists${NC}"
fi

# Get repository URI
REPO_URI=$(awslocal ecr describe-repositories \
  --region "${REGION}" \
  --repository-names "${REPO_NAME}" \
  --query 'repositories[0].repositoryUri' \
  --output text)

echo -e "${YELLOW}🔨 Building and pushing Docker images...${NC}"

# Build and push dagster-taskiq-demo image
echo -e "${YELLOW}Building dagster-taskiq-demo:latest...${NC}"
docker buildx bake dagster-taskiq-demo

FULL_IMAGE_URI="${REPO_URI}:latest"
echo -e "${YELLOW}Pushing to ${FULL_IMAGE_URI}...${NC}"
docker tag "dagster-taskiq-demo:latest" "${FULL_IMAGE_URI}"
awslocal ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${REPO_URI%%/*}"
docker push "${FULL_IMAGE_URI}"

# Build and push taskiq-demo image
echo -e "${YELLOW}Building taskiq-demo:latest...${NC}"
BAKE_TARGET=taskiq-demo docker buildx bake taskiq-demo

TASKIQ_IMAGE_URI="${REPO_URI}:taskiq-demo"
echo -e "${YELLOW}Pushing to ${TASKIQ_IMAGE_URI}...${NC}"
docker tag "taskiq-demo:latest" "${TASKIQ_IMAGE_URI}"
docker push "${TASKIQ_IMAGE_URI}"

# Validate that images were pushed successfully
echo -e "${YELLOW}🔍 Validating pushed images...${NC}"

# Check dagster-taskiq-demo:latest
if awslocal ecr list-images \
  --region "${REGION}" \
  --repository-name "${REPO_NAME}" \
  --query "imageIds[?imageTag=='latest'].imageTag" \
  --output text | grep -q "latest"; then
  echo -e "${GREEN}✅ dagster-taskiq-demo:latest found in ECR${NC}"
else
  echo -e "${RED}❌ dagster-taskiq-demo:latest not found in ECR${NC}"
  exit 1
fi

# Check taskiq-demo:taskiq-demo
if awslocal ecr list-images \
  --region "${REGION}" \
  --repository-name "${REPO_NAME}" \
  --query "imageIds[?imageTag=='taskiq-demo'].imageTag" \
  --output text | grep -q "taskiq-demo"; then
  echo -e "${GREEN}✅ taskiq-demo:taskiq-demo found in ECR${NC}"
else
  echo -e "${RED}❌ taskiq-demo:taskiq-demo not found in ECR${NC}"
  exit 1
fi

echo -e "${GREEN}✅ All images built and pushed successfully!${NC}"
echo -e "${YELLOW}Repository: ${REPO_URI}${NC}"
echo -e "${YELLOW}Images: latest, taskiq-demo${NC}"
