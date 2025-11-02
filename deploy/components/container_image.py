"""Container image build and push component using docker-build provider."""

from __future__ import annotations

from dataclasses import dataclass

import pulumi
import pulumi_docker_build as docker_build
from pulumi_aws import Provider, ecr


@dataclass
class ContainerImage:
    """Container image resources."""

    repository: ecr.Repository
    image: docker_build.Image
    image_uri: pulumi.Output[str]


def create_container_image(
    resource_name: str,
    *,
    provider: Provider,
    project_name: str,
    environment: str,
    context_path: str,
    dockerfile_path: str,
    platform: str = "linux/amd64",
) -> ContainerImage:
    """Build and push a container image to ECR with build caching.

    This component follows Pulumi docker-build best practices:
    - Uses inline caching to store cache metadata in the pushed image
    - Configures cache-from to use previously pushed images
    - Supports multi-platform builds
    - Integrates with ECR authentication

    Args:
        resource_name: Base name for resources
        provider: AWS provider (LocalStack)
        project_name: Project name for naming resources
        environment: Environment name (local, dev, prod)
        context_path: Path to the Docker build context
        dockerfile_path: Path to the Dockerfile relative to context
        platform: Target platform (default: linux/amd64)

    Returns:
        ContainerImage: Bundle containing repository and built image
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

    # Get ECR authorization token
    auth_token = ecr.get_authorization_token_output(
        registry_id=repository.registry_id,
        opts=pulumi.InvokeOptions(provider=provider),
    )

    # Build tags with repository URL
    image_tag = repository.repository_url.apply(lambda url: f"{url}:latest")
    cache_tag = repository.repository_url.apply(lambda url: f"{url}:cache")

    # Build and push image with caching
    image = docker_build.Image(
        f"{resource_name}-image",
        # Build configuration
        context=docker_build.BuildContextArgs(
            location=context_path,
        ),
        dockerfile=docker_build.DockerfileArgs(
            location=dockerfile_path,
        ),
        platforms=[docker_build.Platform(platform)],
        # Push configuration
        push=True,
        tags=[image_tag],
        # Registry authentication for LocalStack ECR
        registries=[
            docker_build.RegistryArgs(
                address=repository.repository_url,
                username=auth_token.user_name,
                password=auth_token.password,
            )
        ],
        # Cache configuration - best practice from documentation
        # Use registry-based cache for better performance
        cache_to=[
            docker_build.CacheToArgs(
                registry=docker_build.CacheToRegistryArgs(
                    ref=cache_tag,
                    image_manifest=True,
                    oci_media_types=True,
                )
            )
        ],
        # Reference the previously pushed cache image
        cache_from=[
            docker_build.CacheFromArgs(
                registry=docker_build.CacheFromRegistryArgs(
                    ref=cache_tag,
                )
            )
        ],
        opts=pulumi.ResourceOptions(provider=provider, depends_on=[repository]),
    )

    # Extract the image URI (digest-based reference)
    image_uri = image.ref

    return ContainerImage(
        repository=repository,
        image=image,
        image_uri=image_uri,
    )
