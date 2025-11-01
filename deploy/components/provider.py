"""Provider helpers for configuring Pulumi against LocalStack."""

from dataclasses import dataclass

import pulumi
import pulumi_aws as aws


@dataclass
class LocalStackProviderConfig:
    """Configuration for the LocalStack AWS provider."""

    region: str
    endpoint: str
    access_key: str
    secret_key: str


def create_localstack_provider(name: str, config: LocalStackProviderConfig) -> aws.Provider:
    """Create a configured AWS provider that points to the LocalStack endpoint.

    Returns:
        aws.Provider: Provider configured for LocalStack endpoints.
    """
    endpoint_mapping = aws.ProviderEndpointArgs(
        ecs=config.endpoint,
        sqs=config.endpoint,
        rds=config.endpoint,
        ec2=config.endpoint,
        iam=config.endpoint,
        sts=config.endpoint,
        logs=config.endpoint,
        cloudwatchlogs=config.endpoint,
    )

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
