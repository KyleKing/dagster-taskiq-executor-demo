"""Provider helpers for configuring Pulumi AWS providers."""

from dataclasses import dataclass

import pulumi
import pulumi_aws as aws


@dataclass
class AwsProviderConfig:
    """AWS provider configuration."""

    region: str
    endpoint: str | None = None  # Optional: for custom endpoints (testing)
    access_key: str | None = None  # Optional: use IAM roles in production
    secret_key: str | None = None  # Optional: use IAM roles in production


# Alias for backwards compatibility
LocalStackProviderConfig = AwsProviderConfig


def create_aws_provider(name: str, config: AwsProviderConfig) -> aws.Provider:
    """Create a configured AWS provider.

    If endpoint is provided, creates a provider configured for custom endpoints (testing).
    Otherwise, creates a standard AWS provider that uses default credentials/region.

    Returns:
        aws.Provider: Configured AWS provider.
    """
    if config.endpoint:
        # Custom endpoint mode (for testing with moto, LocalStack, etc.)
        endpoint_services = [
            "cloudwatchlogs",
            "ec2",
            "ecs",
            "elasticloadbalancing",
            "elasticloadbalancingv2",
            "elb",
            "elbv2",
            "iam",
            "logs",
            "rds",
            "route53",
            "servicediscovery",
            "sqs",
            "sts",
        ]

        endpoint_mapping = aws.ProviderEndpointArgs(**dict.fromkeys(endpoint_services, config.endpoint))

        return aws.Provider(
            name,
            opts=pulumi.ResourceOptions(),
            region=config.region,
            access_key=config.access_key,
            secret_key=config.secret_key,
            endpoints=[endpoint_mapping],
            skip_credentials_validation=True,
            skip_metadata_api_check=True,
            skip_region_validation=True,
            skip_requesting_account_id=True,
            s3_use_path_style=True,
        )

    # Standard AWS provider (uses default credentials from environment/IAM)
    provider_args = {"region": config.region}
    if config.access_key:
        provider_args["access_key"] = config.access_key
    if config.secret_key:
        provider_args["secret_key"] = config.secret_key

    return aws.Provider(
        name,
        opts=pulumi.ResourceOptions(),
        **provider_args,
    )


# Alias for backwards compatibility
create_localstack_provider = create_aws_provider
