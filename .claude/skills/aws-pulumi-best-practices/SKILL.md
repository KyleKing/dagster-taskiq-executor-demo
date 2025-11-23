---
name: aws-pulumi-best-practices
description: Best practices for working with AWS resources using Pulumi, including policies, tagging, security, and version-specific documentation guidance
allowed-tools: "Read,Write,Edit,Bash,Grep,Glob,WebFetch"
version: 1.0.0
---

# AWS Pulumi Best Practices

Comprehensive guide for building secure, maintainable, and cost-effective AWS infrastructure using Pulumi, with emphasis on policy enforcement, resource tagging, security best practices, and navigating version-specific documentation.

## Quick Reference: Documentation Sources

### Finding Version-Specific Documentation

**1. Check installed package version:**
```bash
# Python
pip show pulumi-aws | grep Version

# Node.js
npm list @pulumi/aws

# Output example: Version: 6.15.0
```

**2. Navigate to version-specific docs:**

**Primary sources (in order of preference):**
- **Pulumi Registry** (latest): https://www.pulumi.com/registry/packages/aws/
  - API Reference: https://www.pulumi.com/registry/packages/aws/api-docs/
  - Resource Examples: https://www.pulumi.com/registry/packages/aws/how-to-guides/

- **PyPI** (version-specific): https://pypi.org/project/pulumi-aws/{version}/
  - Example: https://pypi.org/project/pulumi-aws/6.15.0/

- **Python Package Docs**: https://www.pulumi.com/docs/reference/pkg/python/pulumi_aws/
  - Module-specific: https://www.pulumi.com/docs/reference/pkg/python/pulumi_aws/{module}/

- **GitHub Source** (bleeding edge): https://github.com/pulumi/pulumi-aws
  - Release notes: https://github.com/pulumi/pulumi-aws/releases

**3. Search pattern for resources:**
```
https://www.pulumi.com/registry/packages/aws/api-docs/{service}/{resource}/

Examples:
- S3 Bucket: https://www.pulumi.com/registry/packages/aws/api-docs/s3/bucket/
- ECS Service: https://www.pulumi.com/registry/packages/aws/api-docs/ecs/service/
- IAM Role: https://www.pulumi.com/registry/packages/aws/api-docs/iam/role/
```

**4. Check for breaking changes:**
```bash
# View changelog for your version
curl -s https://raw.githubusercontent.com/pulumi/pulumi-aws/master/CHANGELOG.md | less

# Or in your project
pulumi about
```

## Resource Tagging Strategy

### AWS Organizations Tag Policies (Recommended)

Pulumi now integrates directly with AWS Organizations Tag Policies for automatic validation:

**Setup:**
```python
# Activate AWS Organizations Tag Policies pack
# In Pulumi Cloud UI or via CLI
pulumi policy enable aws-organizations-tag-policies

# Start in advisory mode (report violations, don't block)
pulumi policy set-config aws-organizations-tag-policies enforcement-level=advisory

# After remediation, switch to mandatory
pulumi policy set-config aws-organizations-tag-policies enforcement-level=mandatory
```

**Policy automatically validates tags defined in AWS Organizations:**
```bash
# In AWS Organizations console or via AWS CLI
aws organizations put-account-policy \
  --policy-content '{
    "tags": {
      "Environment": {
        "tag_key": {"@@assign": "Environment"},
        "tag_value": {"@@assign": ["prod", "dev", "staging"]}
      },
      "Owner": {
        "tag_key": {"@@assign": "Owner"},
        "enforced_for": {"@@assign": ["ec2:instance", "s3:bucket"]}
      },
      "CostCenter": {
        "tag_key": {"@@assign": "CostCenter"}
      }
    }
  }' \
  --policy-type TAG_POLICY
```

**Pulumi validates at deployment time:**
```bash
$ pulumi up
Previewing update (dev)

Policy Violations:
    [mandatory] aws-organizations-tag-policies (aws-bucket-123)
    Resource 'aws-bucket-123' missing required tag: 'CostCenter'

Do you want to perform this update? no
```

### Default Tags via Provider Configuration

**Apply tags to all resources automatically:**

```python
import pulumi_aws as aws

# Configure default tags at provider level
provider = aws.Provider(
    "aws-provider",
    region="us-east-1",
    default_tags=aws.ProviderDefaultTagsArgs(
        tags={
            "ManagedBy": "Pulumi",
            "Project": pulumi.get_project(),
            "Stack": pulumi.get_stack(),
            "Environment": pulumi.get_stack(),
            "CreatedDate": datetime.now().isoformat(),
        }
    )
)

# All resources using this provider inherit default tags
bucket = aws.s3.Bucket(
    "my-bucket",
    opts=pulumi.ResourceOptions(provider=provider),
    # Additional resource-specific tags
    tags={
        "Owner": "data-team",
        "CostCenter": "engineering-1234"
    }
)

# Final tags: ManagedBy, Project, Stack, Environment, CreatedDate, Owner, CostCenter
```

### Recommended Tag Schema

**Adopt AWS Well-Architected tagging strategy:**

```python
# Standard tag sets for different use cases
TECHNICAL_TAGS = {
    "Name": "",              # Resource identifier
    "Environment": "",       # prod, staging, dev
    "Version": "",           # Application version
    "Tier": "",             # web, app, data
}

AUTOMATION_TAGS = {
    "BackupPolicy": "",      # daily, weekly, none
    "PatchGroup": "",        # Group for patch management
    "SnapshotSchedule": "",  # Backup schedule
    "ShutdownSchedule": "",  # Auto-shutdown for dev/test
}

BUSINESS_TAGS = {
    "Owner": "",            # Team or individual
    "Project": "",          # Project name
    "CostCenter": "",       # Billing allocation
    "Compliance": "",       # PCI, HIPAA, SOC2
}

SECURITY_TAGS = {
    "DataClassification": "",  # public, internal, confidential, restricted
    "Compliance": "",          # Regulatory requirements
    "SecurityZone": "",        # dmz, trusted, restricted
}

# Combine for comprehensive tagging
def create_tags(
    name: str,
    environment: str,
    owner: str,
    cost_center: str,
    **extra_tags
) -> dict:
    """Create standardized tag set for AWS resources."""
    return {
        # Technical
        "Name": name,
        "Environment": environment,
        "ManagedBy": "Pulumi",
        "Project": pulumi.get_project(),
        "Stack": pulumi.get_stack(),

        # Business
        "Owner": owner,
        "CostCenter": cost_center,

        # Automation
        "CreatedDate": datetime.now().isoformat(),

        **extra_tags
    }

# Usage
bucket = aws.s3.Bucket(
    "data-lake",
    tags=create_tags(
        name="data-lake-prod",
        environment="prod",
        owner="data-engineering",
        cost_center="eng-1234",
        DataClassification="confidential",
        BackupPolicy="daily"
    )
)
```

## Security Best Practices

### 1. IAM Policies: Principle of Least Privilege

**Bad - Overly permissive:**
```python
# DON'T DO THIS
role_policy = aws.iam.RolePolicy(
    "bad-policy",
    role=role.id,
    policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": "*",              # All actions
            "Resource": "*"             # All resources
        }]
    })
)
```

**Good - Scoped permissions:**
```python
# Use specific actions and resources
role_policy = aws.iam.RolePolicy(
    "s3-read-policy",
    role=role.id,
    policy=pulumi.Output.json_dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                bucket.arn,
                pulumi.Output.concat(bucket.arn, "/*")
            ]
        }]
    })
)
```

**Best - Use AWS managed policies when possible:**
```python
# Attach AWS managed policy
aws.iam.RolePolicyAttachment(
    "s3-readonly",
    role=role.name,
    policy_arn="arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
)

# For custom needs, use policy data source
policy_doc = aws.iam.get_policy_document(
    statements=[
        aws.iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=["s3:GetObject"],
            resources=[bucket.arn.apply(lambda arn: f"{arn}/*")]
        )
    ]
)
```

### 2. Encryption at Rest (Always Enable)

**S3 Bucket Encryption:**
```python
bucket = aws.s3.Bucket(
    "encrypted-bucket",
    server_side_encryption_configuration=aws.s3.BucketServerSideEncryptionConfigurationArgs(
        rule=aws.s3.BucketServerSideEncryptionConfigurationRuleArgs(
            apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationRuleApplyServerSideEncryptionByDefaultArgs(
                sse_algorithm="AES256",  # Or "aws:kms" for KMS
                kms_master_key_id=kms_key.id  # If using KMS
            ),
            bucket_key_enabled=True  # Reduce KMS costs
        )
    ),
    # Block all public access
    public_access_block_configuration=aws.s3.BucketPublicAccessBlockConfigurationArgs(
        block_public_acls=True,
        block_public_policy=True,
        ignore_public_acls=True,
        restrict_public_buckets=True
    )
)
```

**RDS Encryption:**
```python
db = aws.rds.Instance(
    "database",
    engine="postgres",
    instance_class="db.t3.micro",
    allocated_storage=20,
    storage_encrypted=True,  # Always encrypt
    kms_key_id=kms_key.arn,
    # Additional security
    backup_retention_period=7,
    deletion_protection=True,  # Prevent accidental deletion
    enabled_cloudwatch_logs_exports=["postgresql"],
)
```

**EBS Volume Encryption:**
```python
# Enable encryption by default in region
aws.ebs.DefaultKmsKey(
    "default-ebs-encryption",
    key_arn=kms_key.arn
)

aws.ebs.EncryptionByDefault(
    "enable-ebs-encryption",
    enabled=True
)

# Individual volume
volume = aws.ebs.Volume(
    "encrypted-volume",
    size=100,
    encrypted=True,
    kms_key_id=kms_key.id
)
```

### 3. Secrets Management

**Bad - Hardcoded secrets:**
```python
# DON'T DO THIS
db = aws.rds.Instance(
    "db",
    password="hardcoded-password-123"  # NEVER DO THIS
)
```

**Good - Use AWS Secrets Manager:**
```python
# Create secret
db_password = aws.secretsmanager.Secret(
    "db-password",
    description="Database master password",
    recovery_window_in_days=7  # Allow recovery if accidentally deleted
)

# Generate random password
password = random.RandomPassword(
    "db-password-value",
    length=32,
    special=True
)

# Store in Secrets Manager
aws.secretsmanager.SecretVersion(
    "db-password-version",
    secret_id=db_password.id,
    secret_string=password.result
)

# Use secret in RDS
db = aws.rds.Instance(
    "database",
    password=password.result,  # Pulumi manages securely
    # ...
)

# Reference secret in application
task_definition = aws.ecs.TaskDefinition(
    "app",
    container_definitions=pulumi.Output.json_dumps([{
        "name": "app",
        "image": "myapp:latest",
        "secrets": [{
            "name": "DB_PASSWORD",
            "valueFrom": db_password.arn  # ECS retrieves at runtime
        }]
    }])
)
```

**Alternative - Use Pulumi Config with encryption:**
```bash
# Set encrypted config value
pulumi config set --secret dbPassword "my-secure-password"
```

```python
# Read encrypted value
config = pulumi.Config()
db_password = config.require_secret("dbPassword")

db = aws.rds.Instance(
    "database",
    password=db_password
)
```

### 4. Network Security

**VPC Security Groups:**
```python
# Security group with minimal ingress
app_sg = aws.ec2.SecurityGroup(
    "app-sg",
    description="Application security group",
    vpc_id=vpc.id,
    # No ingress rules by default (deny all inbound)
    ingress=[],  # Add specific rules as needed
    egress=[
        # Allow outbound HTTPS only
        aws.ec2.SecurityGroupEgressArgs(
            protocol="tcp",
            from_port=443,
            to_port=443,
            cidr_blocks=["0.0.0.0/0"],
            description="HTTPS outbound"
        )
    ],
    tags=create_tags(
        name="app-security-group",
        environment="prod",
        owner="platform-team",
        cost_center="eng-1234"
    )
)

# Add ingress rule from specific source
aws.ec2.SecurityGroupRule(
    "app-from-lb",
    type="ingress",
    security_group_id=app_sg.id,
    protocol="tcp",
    from_port=8080,
    to_port=8080,
    source_security_group_id=lb_sg.id,  # Only from load balancer
    description="Application port from load balancer"
)
```

**Network ACLs for Defense in Depth:**
```python
# Private subnet NACL
private_nacl = aws.ec2.NetworkAcl(
    "private-nacl",
    vpc_id=vpc.id,
    subnet_ids=[subnet.id for subnet in private_subnets],
    # Explicit allow rules
    ingress=[
        aws.ec2.NetworkAclIngressArgs(
            protocol="tcp",
            rule_no=100,
            action="allow",
            cidr_block=vpc.cidr_block,  # Only from VPC
            from_port=443,
            to_port=443
        )
    ],
    egress=[
        aws.ec2.NetworkAclEgressArgs(
            protocol="-1",  # All protocols
            rule_no=100,
            action="allow",
            cidr_block="0.0.0.0/0",
            from_port=0,
            to_port=0
        )
    ]
)
```

## Policy as Code with CrossGuard

### Enable AWS Best Practices Policy Pack

**Install and enable AWSGuard:**
```bash
# Enable pre-built AWS policy pack
pulumi policy enable awsguard

# Configure enforcement level
pulumi policy set-config awsguard enforcement-level=mandatory
```

### Custom Policy Pack Example

```typescript
// policy/index.ts
import * as aws from "@pulumi/aws";
import { PolicyPack, validateResourceOfType } from "@pulumi/policy";

const policies = new PolicyPack("aws-security-policies", {
    policies: [
        {
            name: "s3-no-public-read",
            description: "S3 buckets must not allow public read access",
            enforcementLevel: "mandatory",
            validateResource: validateResourceOfType(aws.s3.Bucket, (bucket, args, reportViolation) => {
                if (bucket.acl === "public-read" || bucket.acl === "public-read-write") {
                    reportViolation("S3 buckets must not have public ACLs");
                }
            }),
        },
        {
            name: "rds-encryption-required",
            description: "RDS instances must be encrypted",
            enforcementLevel: "mandatory",
            validateResource: validateResourceOfType(aws.rds.Instance, (instance, args, reportViolation) => {
                if (instance.storageEncrypted !== true) {
                    reportViolation("RDS instances must have storage encryption enabled");
                }
            }),
        },
        {
            name: "required-tags",
            description: "All resources must have required tags",
            enforcementLevel: "advisory",
            validateResource: (args, reportViolation) => {
                const requiredTags = ["Environment", "Owner", "CostCenter"];
                const resourceTags = args.props.tags || {};

                const missingTags = requiredTags.filter(tag => !resourceTags[tag]);

                if (missingTags.length > 0) {
                    reportViolation(`Missing required tags: ${missingTags.join(", ")}`);
                }
            },
        },
    ],
});
```

**Enable custom policy pack:**
```bash
cd policy && npm install
pulumi policy publish
pulumi policy enable my-org/aws-security-policies latest
```

## Cost Optimization

### 1. Right-Sizing Instances

```python
# Use burstable instances for variable workloads
instance = aws.ec2.Instance(
    "web-server",
    instance_type="t3.medium",  # Burstable, cost-effective
    credit_specification=aws.ec2.InstanceCreditSpecificationArgs(
        cpu_credits="unlimited"  # Or "standard" for predictable costs
    )
)

# Use Spot instances for fault-tolerant workloads
spot_request = aws.ec2.SpotInstanceRequest(
    "batch-worker",
    instance_type="c5.large",
    spot_price="0.05",  # Max price per hour
    wait_for_fulfillment=True
)
```

### 2. Lifecycle Policies for S3

```python
bucket = aws.s3.Bucket(
    "data-bucket",
    lifecycle_rules=[
        # Transition to cheaper storage classes
        aws.s3.BucketLifecycleRuleArgs(
            enabled=True,
            transitions=[
                aws.s3.BucketLifecycleRuleTransitionArgs(
                    days=30,
                    storage_class="STANDARD_IA"  # Infrequent Access
                ),
                aws.s3.BucketLifecycleRuleTransitionArgs(
                    days=90,
                    storage_class="GLACIER"  # Archive
                ),
            ],
            # Delete old versions
            noncurrent_version_expiration=aws.s3.BucketLifecycleRuleNoncurrentVersionExpirationArgs(
                days=90
            )
        ),
        # Delete expired delete markers
        aws.s3.BucketLifecycleRuleArgs(
            enabled=True,
            expiration=aws.s3.BucketLifecycleRuleExpirationArgs(
                expired_object_delete_marker=True
            )
        )
    ]
)
```

### 3. Cost Allocation Tags

```python
# Enable cost allocation tags
cost_tags = {
    "CostCenter": "engineering-1234",
    "Project": "data-platform",
    "Environment": "prod",
    "Team": "data-engineering"
}

# Apply to all billable resources
bucket = aws.s3.Bucket("data-bucket", tags=cost_tags)
db = aws.rds.Instance("database", tags=cost_tags)
cluster = aws.ecs.Cluster("cluster", tags=cost_tags)

# Use tags in AWS Cost Explorer for cost breakdowns
```

## Monitoring and Observability

### CloudWatch Alarms

```python
# High-level alarm for critical metrics
alarm = aws.cloudwatch.MetricAlarm(
    "high-cpu-alarm",
    comparison_operator="GreaterThanThreshold",
    evaluation_periods=2,
    metric_name="CPUUtilization",
    namespace="AWS/EC2",
    period=300,  # 5 minutes
    statistic="Average",
    threshold=80,
    alarm_description="Alert when CPU exceeds 80%",
    dimensions={
        "InstanceId": instance.id
    },
    alarm_actions=[sns_topic.arn],  # Send to SNS topic
    tags=create_tags(
        name="cpu-alarm",
        environment="prod",
        owner="platform-team",
        cost_center="eng-1234"
    )
)
```

### CloudWatch Logs

```python
# Log group with retention
log_group = aws.cloudwatch.LogGroup(
    "app-logs",
    retention_in_days=7,  # Reduce costs for non-critical logs
    kms_key_id=kms_key.id,  # Encrypt logs
    tags=create_tags(
        name="application-logs",
        environment="prod",
        owner="app-team",
        cost_center="eng-1234"
    )
)

# Metric filter for custom metrics
metric_filter = aws.cloudwatch.LogMetricFilter(
    "error-count",
    log_group_name=log_group.name,
    pattern="ERROR",
    metric_transformation=aws.cloudwatch.LogMetricFilterMetricTransformationArgs(
        name="ErrorCount",
        namespace="CustomApp",
        value="1"
    )
)
```

## Infrastructure Organization Patterns

### 1. Component Resources (Recommended)

**Create reusable infrastructure components:**

```python
# components/vpc.py
class VpcComponent(pulumi.ComponentResource):
    """Reusable VPC component with best practices built-in."""

    def __init__(
        self,
        name: str,
        cidr_block: str,
        availability_zones: list[str],
        tags: dict,
        opts: pulumi.ResourceOptions = None
    ):
        super().__init__("custom:network:VPC", name, {}, opts)

        # VPC
        self.vpc = aws.ec2.Vpc(
            f"{name}-vpc",
            cidr_block=cidr_block,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            tags={**tags, "Name": f"{name}-vpc"},
            opts=pulumi.ResourceOptions(parent=self)
        )

        # Internet Gateway
        self.igw = aws.ec2.InternetGateway(
            f"{name}-igw",
            vpc_id=self.vpc.id,
            tags={**tags, "Name": f"{name}-igw"},
            opts=pulumi.ResourceOptions(parent=self)
        )

        # Public subnets
        self.public_subnets = []
        for i, az in enumerate(availability_zones):
            subnet = aws.ec2.Subnet(
                f"{name}-public-{az}",
                vpc_id=self.vpc.id,
                cidr_block=f"10.0.{i}.0/24",
                availability_zone=az,
                map_public_ip_on_launch=True,
                tags={**tags, "Name": f"{name}-public-{az}"},
                opts=pulumi.ResourceOptions(parent=self)
            )
            self.public_subnets.append(subnet)

        self.register_outputs({
            "vpc_id": self.vpc.id,
            "public_subnet_ids": [s.id for s in self.public_subnets]
        })

# Usage
vpc = VpcComponent(
    "prod-vpc",
    cidr_block="10.0.0.0/16",
    availability_zones=["us-east-1a", "us-east-1b"],
    tags=create_tags(
        name="prod-vpc",
        environment="prod",
        owner="platform-team",
        cost_center="eng-1234"
    )
)
```

### 2. Stack References for Multi-Stack Dependencies

```python
# Stack: networking (defines VPC)
pulumi.export("vpc_id", vpc.id)
pulumi.export("private_subnet_ids", [s.id for s in private_subnets])

# Stack: applications (consumes VPC from networking stack)
config = pulumi.Config()
networking_stack = pulumi.StackReference(
    f"{pulumi.get_organization()}/networking/{config.require('networkingStack')}"
)

vpc_id = networking_stack.get_output("vpc_id")
subnet_ids = networking_stack.get_output("private_subnet_ids")

# Use outputs in current stack
app = aws.ecs.Service(
    "app",
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=subnet_ids,
        security_groups=[app_sg.id]
    )
)
```

## Common Anti-Patterns to Avoid

### ❌ Anti-Pattern 1: Not Using Stack Outputs
```python
# Bad: Hardcoded resource IDs
vpc_id = "vpc-1234567890"  # What if VPC changes?
```
```python
# Good: Use stack outputs
pulumi.export("vpc_id", vpc.id)
```

### ❌ Anti-Pattern 2: Ignoring Resource Dependencies
```python
# Bad: Manual dependency management
db = aws.rds.Instance("db", subnet_group_name="my-subnet-group")
```
```python
# Good: Explicit dependencies
subnet_group = aws.rds.SubnetGroup("subnet-group", subnet_ids=subnet_ids)
db = aws.rds.Instance(
    "db",
    subnet_group_name=subnet_group.name,
    opts=pulumi.ResourceOptions(depends_on=[subnet_group])
)
```

### ❌ Anti-Pattern 3: Not Using Resource Transformations
```python
# Bad: Repeating tags on every resource
bucket1 = aws.s3.Bucket("b1", tags={"Environment": "prod", "Owner": "team"})
bucket2 = aws.s3.Bucket("b2", tags={"Environment": "prod", "Owner": "team"})
```
```python
# Good: Use provider default_tags or transformations
pulumi.runtime.register_stack_transformation(lambda args: (
    pulumi.ResourceTransformationResult(
        props={**args.props, "tags": {**args.props.get("tags", {}), **COMMON_TAGS}},
        opts=args.opts
    )
))
```

## Version Management

### Pin Provider Versions

```python
# requirements.txt or pyproject.toml
pulumi>=3.0.0,<4.0.0
pulumi-aws>=6.0.0,<7.0.0  # Pin to major version

# Or specific version
pulumi-aws==6.15.0
```

### Upgrade Strategy

```bash
# 1. Check for new versions
pip list --outdated | grep pulumi

# 2. Review changelog
curl -s https://github.com/pulumi/pulumi-aws/releases

# 3. Upgrade in dev environment first
pip install --upgrade pulumi-aws

# 4. Test with preview
pulumi preview --diff

# 5. Review breaking changes
# Look for "replacing" resources (may cause downtime)

# 6. Deploy to production
pulumi up
```

## References

- **AWS Well-Architected Framework**: https://aws.amazon.com/architecture/well-architected/
- **Pulumi AWS Best Practices**: https://www.pulumi.com/docs/clouds/aws/guides/
- **AWS Tagging Best Practices**: https://docs.aws.amazon.com/whitepapers/latest/tagging-best-practices/
- **Pulumi CrossGuard**: https://www.pulumi.com/crossguard/
- **AWSGuard Policies**: https://github.com/pulumi/pulumi-policy-aws
- **AWS Security Best Practices**: https://docs.aws.amazon.com/security/
