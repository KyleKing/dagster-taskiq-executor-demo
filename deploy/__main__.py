import pulumi
from pulumi import ResourceOptions
import pulumi_aws as aws

config = pulumi.Config()

region = config.get("region") or "us-east-1"
endpoint = config.get("endpoint") or "http://localhost:4566"
access_key = config.get("accessKey") or "test"
secret_key = config.get("secretKey") or "test"
queue_name = config.get("queueName") or "demo-queue"
cluster_name = config.get("clusterName") or "demo-cluster"

# Configure the AWS provider to interact with LocalStack instead of AWS.
provider = aws.Provider(
    "localstack",
    region=region,
    access_key=access_key,
    secret_key=secret_key,
    endpoints=[
        aws.ProviderEndpointArgs(service="ecs", url=endpoint),
        aws.ProviderEndpointArgs(service="sqs", url=endpoint),
        aws.ProviderEndpointArgs(service="sts", url=endpoint),
    ],
    skip_credentials_validation=True,
    skip_metadata_api_check=True,
    skip_region_validation=True,
    skip_requesting_account_id=True,
    s3_force_path_style=True,
)

queue = aws.sqs.Queue(
    "queue",
    name=queue_name,
    opts=ResourceOptions(provider=provider),
)

cluster = aws.ecs.Cluster(
    "cluster",
    name=cluster_name,
    opts=ResourceOptions(provider=provider),
)

pulumi.export("queueUrl", queue.id)
pulumi.export("queueArn", queue.arn)
pulumi.export("clusterArn", cluster.arn)
