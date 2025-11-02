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


def create_buildkit_config() -> str:
    """Create BuildKit TOML config for insecure registry.

    This allows BuildKit to push to LocalStack ECR over HTTP without TLS.
    """
    return """
# Allow insecure (HTTP) registry for LocalStack
[registry."host.docker.internal:4566"]
  http = true
  insecure = true
"""


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

    # Get ECR authorization token for LocalStack.
    # LocalStack doesn't properly handle registry_id parameter, so we call without it.
    # We still defer until after repository creation to ensure ECR service is initialized.
    auth_token = repository.registry_id.apply(
        lambda _: ecr.get_authorization_token(
            opts=pulumi.InvokeOptions(provider=provider),
        )
    )
    username = auth_token.apply(lambda token: token.user_name)
    raw_password = auth_token.apply(lambda token: token.password)
    password = pulumi.Output.secret(raw_password)

    # For LocalStack, we need to use host.docker.internal:4566 for all registry operations since
    # docker-build runs in a BuildKit container. The host.docker.internal hostname allows containers
    # to reach the host's network where LocalStack is running.
    # Use http:// explicitly to avoid TLS/HTTPS issues with LocalStack's self-signed certificate
    registry_address = pulumi.Output.concat("http://host.docker.internal:4566")
    image_tag = pulumi.Output.concat(f"host.docker.internal:4566/{project_name}-{environment}:latest")

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
        # Use localhost:4566 as the actual registry address for network connectivity
        registries=[
            docker_build.RegistryArgs(
                address=registry_address,
                username=username,
                password=password,
            )
        ],
        # Cache configuration - best practice from documentation
        # Use registry-based cache for better performance
        # Disable cache for now due to LocalStack networking issues
        # cache_to=[
        #     docker_build.CacheToArgs(
        #         registry=docker_build.CacheToRegistryArgs(
        #             ref=pulumi.Output.concat(f"host.docker.internal:4566/{project_name}-{environment}:cache"),
        #             image_manifest=True,
        #             oci_media_types=True,
        #         )
        #     )
        # ],
        # cache_from=[
        #     docker_build.CacheFromArgs(
        #         registry=docker_build.CacheFromRegistryArgs(
        #             ref=pulumi.Output.concat(f"host.docker.internal:4566/{project_name}-{environment}:cache"),
        #         )
        #     )
        # ],
        opts=pulumi.ResourceOptions(provider=provider, depends_on=[repository]),
    )

    # Extract the image digest and construct the proper ECR URI
    # We pushed using localhost:4566, but ECS tasks need to reference the ECR repository URL
    # So we construct a URI using the repository URL + the digest from the pushed image
    image_digest = image.digest
    image_uri = pulumi.Output.all(repository.repository_url, image_digest).apply(
        lambda args: f"{args[0]}@{args[1]}"
    )

    return ContainerImage(
        repository=repository,
        image=image,
        image_uri=image_uri,
    )
