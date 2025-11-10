"""ECR repository component - creates repository without building images."""

from dataclasses import dataclass

import pulumi
from pulumi_aws import Provider, ecr


@dataclass
class ECRRepository:
    """ECR repository resources."""

    repository: ecr.Repository
    repository_uri: pulumi.Output[str]


def create_ecr_repository(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
) -> ECRRepository:
    """Create an ECR repository without building images.

    This component only provisions the ECR repository. Images should be built
    and pushed separately using Docker + awslocal CLI.

    For LocalStack development workflow:
    1. Create repository with Pulumi (this function)
    2. Build and push images using the provided script: ./scripts/build-and-push.sh
    3. Reference the image URI in your infrastructure code

    Args:
        resource_name: Base name for resources
        provider: AWS provider (LocalStack)
        project_name: Project name for naming resources
        environment: Environment name (local, dev, prod)

    Returns:
        ECRRepository: Bundle containing repository metadata
    """
    # Create ECR repository
    repository = ecr.Repository(
        f"{resource_name}-repo",
        name=f"{project_name}-{environment}",
        image_tag_mutability="MUTABLE",
        image_scanning_configuration=ecr.RepositoryImageScanningConfigurationArgs(
            scan_on_push=True,
        ),
        force_delete=True,  # Allow cleanup in local development
        opts=pulumi.ResourceOptions(provider=provider),
    )

    # Construct the expected image URI
    # For LocalStack, this will be in the format:
    # 000000000000.dkr.ecr.{region}.localhost.localstack.cloud:4566/{repo-name}:latest
    repository_uri = repository.repository_url.apply(lambda url: f"{url}:latest")

    return ECRRepository(
        repository=repository,
        repository_uri=repository_uri,
    )
