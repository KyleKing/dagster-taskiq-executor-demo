---
name: pulumi-testing
description: Guide for writing effective Pulumi infrastructure tests using pytest with minimal mocking and high coverage (>80%)
allowed-tools: "Read,Write,Edit,Bash,Grep,Glob"
version: 2.0.0
---

# Pulumi Infrastructure Testing with Pytest

Guide for writing effective infrastructure tests for Pulumi programs following the principle: **fewest tests that reach >80% coverage at a high level with minimal mocking**.

## Testing Philosophy

**Prefer integration tests over unit tests** - Real infrastructure validation is more valuable than mocked resource validation. Use the Automation API to create ephemeral stacks that deploy actual resources, validate behavior, then tear down.

**Minimal mocking principle** - Only mock when absolutely necessary (e.g., external dependencies outside your control, expensive resources in CI). Most infrastructure testing should validate real resource properties and interactions.

**High-level coverage** - Focus on testing critical paths and resource interactions rather than exhaustive property validation. Aim for >80% coverage of important infrastructure behaviors with fewer, more comprehensive tests.

## Testing Approach: Three-Tier Strategy

### 1. Integration Tests (Primary Focus - 70% of test effort)

Use Pulumi's Automation API to deploy ephemeral stacks and validate real infrastructure:

**Pytest Fixture Pattern:**
```python
import pytest
from pulumi import automation as auto

@pytest.fixture(scope="module")
def pulumi_stack():
    """Deploy ephemeral Pulumi stack for testing."""
    # Setup: Create and deploy stack
    stack_name = f"test-{uuid.uuid4().hex[:8]}"
    project_name = "my-project"

    stack = auto.create_or_select_stack(
        stack_name=stack_name,
        project_name=project_name,
        program=lambda: pulumi_program(),  # Your infrastructure code
    )

    # Configure stack
    stack.set_config("aws:region", auto.ConfigValue("us-east-1"))

    # Deploy
    up_result = stack.up(on_output=print)

    # Yield stack and outputs to tests
    yield {
        "stack": stack,
        "outputs": up_result.outputs,
    }

    # Teardown: Destroy resources
    stack.destroy(on_output=print)
    stack.workspace.remove_stack(stack_name)
```

**Integration Test Pattern:**
```python
def test_infrastructure_deployment(pulumi_stack):
    """Validate deployed infrastructure using cloud provider SDKs."""
    outputs = pulumi_stack["outputs"]

    # Get resource identifiers from stack outputs
    bucket_name = outputs["bucket_name"].value
    queue_url = outputs["queue_url"].value

    # Validate using boto3 (or other provider SDKs)
    import boto3

    s3 = boto3.client("s3")
    sqs = boto3.client("sqs")

    # Verify S3 bucket exists and has correct configuration
    bucket_versioning = s3.get_bucket_versioning(Bucket=bucket_name)
    assert bucket_versioning["Status"] == "Enabled"

    # Verify SQS queue has correct attributes
    queue_attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["VisibilityTimeout", "MessageRetentionPeriod"]
    )
    assert int(queue_attrs["Attributes"]["VisibilityTimeout"]) == 300

    # Test end-to-end interaction
    sqs.send_message(QueueUrl=queue_url, MessageBody="test")
    messages = sqs.receive_message(QueueUrl=queue_url)
    assert len(messages.get("Messages", [])) == 1
```

**When to use:**
- Testing resource creation and configuration
- Validating cross-resource interactions (e.g., IAM permissions work)
- End-to-end infrastructure workflows
- Security configuration validation

### 2. Property Tests (20% of test effort)

Run lightweight assertions during stack deployment without full teardown:

```python
@pulumi.runtime.test
def test_bucket_encryption():
    """Property test runs during deployment to validate resource properties."""
    # Import your infrastructure module
    from infra import bucket

    # Validate properties (runs during preview/up)
    def check_encryption(args):
        server_side_encryption = args["server_side_encryption_configuration"]
        assert server_side_encryption is not None, "S3 bucket must have encryption"
        return args

    # Apply validation
    bucket.server_side_encryption_configuration.apply(check_encryption)
```

**When to use:**
- Quick validation of critical security properties
- Checking required tags or naming conventions
- Validating resource dependencies are correct

### 3. Unit Tests with Mocking (10% of test effort - only when necessary)

Use mocks sparingly for fast feedback on logic:

```python
import pulumi
from pulumi.runtime import Mocks

class MyMocks(Mocks):
    def new_resource(self, args):
        # Return mocked resource outputs
        outputs = args.inputs
        if args.typ == "aws:s3/bucket:Bucket":
            outputs["arn"] = f"arn:aws:s3:::{args.name}"
        return [args.name, outputs]

    def call(self, args):
        # Mock provider function calls
        if args.token == "aws:s3/getBucket:getBucket":
            return {"bucket": args.inputs["bucket"]}
        return {}

@pytest.fixture
def mocked_pulumi():
    """Enable mocking mode for unit tests."""
    pulumi.runtime.set_mocks(MyMocks())

def test_infrastructure_logic(mocked_pulumi):
    """Test infrastructure logic without deploying resources."""
    import infra

    # Test returns immediately with mocked outputs
    @pulumi.runtime.test
    def check_outputs():
        # Access mocked resource properties
        assert infra.bucket.bucket.apply(lambda b: b.startswith("my-"))
```

**When to use (sparingly):**
- Testing conditional resource creation logic
- Validating input transformations
- Fast feedback during development (not for CI validation)

## Test Organization

**Directory Structure:**
```
project/
├── infra/
│   ├── __init__.py
│   ├── networking.py
│   ├── storage.py
│   └── compute.py
├── tests/
│   ├── integration/
│   │   ├── test_networking_deployment.py
│   │   ├── test_storage_deployment.py
│   │   └── test_end_to_end.py
│   ├── property/
│   │   └── test_security_properties.py
│   └── unit/  # Only if absolutely needed
│       └── test_conditional_logic.py
├── Pulumi.yaml
└── pytest.ini
```

**Pytest Configuration (pytest.ini):**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    integration: Integration tests deploying real infrastructure
    property: Property tests during deployment
    unit: Fast unit tests with mocking
    slow: Tests that take >60 seconds
asyncio_mode = auto

# Run integration tests by default
addopts = -v --tb=short -m "not slow"
```

## Coverage Strategy

**Focus on high-value coverage:**

1. **Critical resource validation (30% coverage effort)**
   - Security configurations (encryption, IAM policies)
   - Network configurations (VPC, security groups)
   - Data persistence (backups, replication)

2. **Cross-resource interactions (40% coverage effort)**
   - IAM role can access S3 bucket
   - Lambda can read from SQS queue
   - ECS tasks can communicate with RDS

3. **End-to-end workflows (30% coverage effort)**
   - Deployment succeeds without errors
   - Application can perform its primary function
   - Monitoring and logging are functional

**Skip low-value tests:**
- Don't test every resource property (trust Pulumi/Terraform provider)
- Don't test cloud provider behavior (trust AWS/Azure/GCP)
- Don't exhaustively test all tag combinations

## LocalStack Integration (for cost-effective testing)

For CI/CD or local development, use LocalStack to test against AWS-compatible services:

```python
@pytest.fixture(scope="session")
def localstack_endpoint():
    """Start LocalStack for testing."""
    # Assumes LocalStack running in Docker
    return "http://localhost:4566"

@pytest.fixture(scope="module")
def pulumi_stack_localstack(localstack_endpoint):
    """Deploy to LocalStack instead of real AWS."""
    stack = auto.create_or_select_stack(...)

    # Configure to use LocalStack
    stack.set_config("aws:region", auto.ConfigValue("us-east-1"))
    stack.set_config("aws:endpoints", auto.ConfigValue([{
        "s3": localstack_endpoint,
        "sqs": localstack_endpoint,
        "dynamodb": localstack_endpoint,
    }]))

    up_result = stack.up(on_output=print)
    yield {"stack": stack, "outputs": up_result.outputs}
    stack.destroy(on_output=print)
```

## LocalStack State Management (Critical for Development)

### The Problem: Lifecycle Mismatch

**LocalStack** (Docker container) is **ephemeral** - it can be destroyed and recreated easily.
**Pulumi state** (on your laptop) is **persistent** - it survives across LocalStack restarts.

This mismatch causes **state divergence** when:
- LocalStack container restarts (resources gone, but Pulumi thinks they exist)
- LocalStack Docker volume is deleted
- LocalStack crashes or becomes corrupted
- You switch between LocalStack instances

**Symptoms of divergence:**
```
Error: reading S3 Bucket (my-bucket): NotFound: Not Found
Error: error reading SQS Queue (my-queue): AWS.SimpleQueueService.NonExistentQueue
pulumi:pulumi:Stack my-project-dev **failed** 1 error
```

### Solution 1: Development Workflow Script

Use the provided `{baseDir}/scripts/localstack-dev.sh` utility:

**Common operations:**
```bash
# Check status of LocalStack and Pulumi
./scripts/localstack-dev.sh status

# Start LocalStack
./scripts/localstack-dev.sh start

# After LocalStack container restart (most common issue)
./scripts/localstack-dev.sh restart
./scripts/localstack-dev.sh sync    # Sync Pulumi state with reality

# Check if state is diverged
./scripts/localstack-dev.sh check

# Before making risky changes
./scripts/localstack-dev.sh backup
pulumi up
# If it breaks:
./scripts/localstack-dev.sh restore <backup-file>

# Nuclear option: destroy everything and start fresh
./scripts/localstack-dev.sh fresh-start
```

**Script features:**
- Automatically starts LocalStack with persistence enabled
- Detects state divergence
- Syncs Pulumi state with LocalStack reality using `pulumi refresh`
- Backs up and restores Pulumi state
- Provides fresh-start workflow for complete reset

### Solution 2: Automatic Pytest Fixtures

Add automatic state synchronization to your tests using `{baseDir}/scripts/pytest_localstack_sync.py`:

**Setup in conftest.py:**
```python
# tests/conftest.py
import sys
from pathlib import Path

# Add skills scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude/skills/pulumi-testing/scripts"))

# Import fixtures
from pytest_localstack_sync import (
    ensure_localstack,
    localstack_state_sync,
    fresh_localstack,
    localstack_endpoint
)
```

**Benefits:**
- `ensure_localstack` (autouse) - Automatically starts LocalStack before all tests
- `localstack_state_sync` - Syncs state before/after each test
- `fresh_localstack` - Provides completely fresh state for test isolation
- Automatically detects and reports state divergence errors

**Usage in tests:**
```python
import pytest

# Automatic sync for this test
@pytest.mark.state_sync
def test_deployment(localstack_state_sync):
    """State is synced before and after this test."""
    # Deploy infrastructure
    stack.up()
    # Test something
    assert ...

# Completely isolated test
@pytest.mark.fresh_state
def test_from_scratch(fresh_localstack):
    """Fresh LocalStack, no existing resources."""
    # Perfect for testing initial deployment
    ...
```

### Solution 3: LocalStack with Persistence

**Configure LocalStack to persist data across restarts:**

```bash
# docker-compose.yml
version: "3.8"
services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - SERVICES=s3,sqs,dynamodb,iam,sts,lambda,ecs,rds,ec2
      - DEBUG=1
      - PERSISTENCE=1                  # Enable persistence
      - DATA_DIR=/tmp/localstack/data
    volumes:
      - localstack-data:/tmp/localstack  # Persist data
volumes:
  localstack-data:
```

**Benefits:**
- LocalStack state survives container restarts
- Reduces state divergence issues
- Faster restart (don't need to redeploy)

**Limitations:**
- Still diverges if volume is deleted
- Persistence has some bugs/limitations in LocalStack
- Not all services persist perfectly

### Solution 4: State Backend Strategy

**Use file:// backend with explicit state file:**

```yaml
# Pulumi.yaml
name: my-project
runtime: python
backend:
  url: file://./pulumi-state  # Local directory

# .gitignore
pulumi-state/
```

**Benefits:**
- State is in your project directory
- Easy to see when state changes
- Can be backed up/restored easily
- Clear separation per project

**Delete state when LocalStack is destroyed:**
```bash
# When doing fresh start
docker rm -f localstack
docker volume rm localstack-data
rm -rf pulumi-state/  # Also delete state
pulumi stack init dev  # Recreate stack
pulumi up  # Fresh deployment
```

### Solution 5: Pulumi Refresh Automation

**Add pre-deployment refresh to catch divergence early:**

```bash
# deploy.sh
#!/bin/bash
set -e

# Always refresh before deploy
pulumi refresh --yes

# Then deploy
pulumi up --yes
```

**Or in Automation API:**
```python
def deploy_with_auto_sync(stack):
    """Deploy with automatic state synchronization."""
    try:
        # Try refresh first
        stack.refresh()
    except Exception as e:
        print(f"Refresh failed: {e}")
        print("State may be diverged - attempting to continue")

    # Deploy
    up_result = stack.up()
    return up_result
```

### Solution 6: State Divergence Recovery Script

Use `{baseDir}/scripts/sync-localstack-state.py` for advanced recovery:

```bash
# Check for divergence
python scripts/sync-localstack-state.py --check

# Try to fix by refreshing
python scripts/sync-localstack-state.py --refresh

# Nuclear option: clear state and redeploy
python scripts/sync-localstack-state.py --reset
```

**What it does:**
- Detects if LocalStack is running
- Compares Pulumi state with LocalStack reality
- Offers recovery options:
  - `--refresh`: Update Pulumi state from LocalStack (safe)
  - `--reset`: Clear everything and redeploy (nuclear)
- Backs up state before destructive operations

### Best Practices for LocalStack Development

**1. Always use the workflow script:**
```bash
# Don't do this:
docker restart localstack
pulumi up  # ← Will fail with state divergence

# Do this:
./scripts/localstack-dev.sh restart
./scripts/localstack-dev.sh sync
pulumi up  # ← Works correctly
```

**2. Add state sync to your development workflow:**
```bash
# .envrc (for direnv) or .bashrc
alias pup='./scripts/localstack-dev.sh sync && pulumi up'
alias pdown='pulumi destroy --yes && ./scripts/localstack-dev.sh sync'
alias preset='./scripts/localstack-dev.sh fresh-start'
```

**3. Use pre-commit hooks:**
```bash
# .git/hooks/pre-commit
#!/bin/bash
# Check for state divergence before committing
./scripts/localstack-dev.sh check || {
    echo "WARNING: Pulumi state may be diverged from LocalStack"
    echo "Run: ./scripts/localstack-dev.sh sync"
    exit 1
}
```

**4. Document the workflow in your README:**
```markdown
## LocalStack Development

**First time setup:**
```bash
./scripts/localstack-dev.sh start
pulumi stack init dev
pulumi up
```

**After LocalStack restart:**
```bash
./scripts/localstack-dev.sh restart
./scripts/localstack-dev.sh sync
```

**When things break:**
```bash
./scripts/localstack-dev.sh check    # Diagnose
./scripts/localstack-dev.sh sync     # Try to fix
./scripts/localstack-dev.sh fresh-start  # Nuclear option
```
```

**5. Use makefiles for common operations:**
```makefile
# Makefile
.PHONY: localstack-start localstack-sync localstack-reset

localstack-start:
	./scripts/localstack-dev.sh start

localstack-sync:
	./scripts/localstack-dev.sh sync

localstack-reset:
	./scripts/localstack-dev.sh fresh-start

test-local: localstack-sync
	PULUMI_CONFIG_PASSPHRASE="" pytest tests/ -m localstack
```

**6. Test state recovery in CI:**
```yaml
# .github/workflows/test.yml
- name: Test state recovery
  run: |
    # Deploy infrastructure
    pulumi up --yes

    # Simulate LocalStack failure
    docker restart localstack
    sleep 10

    # Verify recovery works
    ./scripts/localstack-dev.sh sync
    pulumi refresh --yes
```

### Common Scenarios and Solutions

**Scenario 1: LocalStack container restarted**
```bash
$ pulumi up
Error: reading S3 Bucket (my-bucket): NotFound: Not Found

# Solution:
$ ./scripts/localstack-dev.sh restart  # Ensure LocalStack is running
$ ./scripts/localstack-dev.sh sync     # Sync state
$ pulumi up                             # Now works
```

**Scenario 2: Switched to different LocalStack instance**
```bash
# You're using a different LocalStack (e.g., different Docker container)
$ ./scripts/localstack-dev.sh check
Diverged: True
Reason: Refresh failed - likely state divergence

# Solution:
$ ./scripts/localstack-dev.sh fresh-start  # Nuclear option
# This destroys everything and redeploys
```

**Scenario 3: State file corrupted**
```bash
$ pulumi up
error: failed to load checkpoint: ...

# Solution:
$ ls pulumi-state-backup-*.json  # Find recent backup
$ ./scripts/localstack-dev.sh restore pulumi-state-backup-dev-20250115.json
```

**Scenario 4: Want to test deployment from scratch**
```bash
# Option 1: Use fresh_localstack fixture in tests
@pytest.mark.fresh_state
def test_initial_deployment(fresh_localstack):
    ...

# Option 2: Manual fresh start
$ ./scripts/localstack-dev.sh fresh-start
```

**Scenario 5: LocalStack works but Pulumi is confused**
```bash
# Pulumi thinks resources exist but they don't in LocalStack
$ pulumi refresh --yes  # Update state from reality

# If refresh fails:
$ python scripts/sync-localstack-state.py --reset
```

### Utilities Reference

**Location:** `.claude/skills/pulumi-testing/scripts/`

**Files:**
- `localstack-dev.sh` - Main development workflow script
- `sync-localstack-state.py` - Advanced state synchronization
- `pytest_localstack_sync.py` - Pytest fixtures for automatic sync

**Make scripts executable:**
```bash
chmod +x .claude/skills/pulumi-testing/scripts/*.sh
```

## Running Tests

**Local development (fast feedback):**
```bash
# Run only fast tests
pytest -m "not slow and not integration"

# Run integration tests against LocalStack
LOCALSTACK=1 pytest -m integration

# Run specific test file
pytest tests/integration/test_networking_deployment.py -v
```

**CI/CD pipeline (comprehensive validation):**
```bash
# Run all tests including integration against real cloud
pytest -m "integration or property" --maxfail=1

# With coverage reporting
pytest --cov=infra --cov-report=term-missing --cov-report=xml
```

## Best Practices

1. **Use stack outputs to reference resources** - Don't hardcode resource names; use Pulumi outputs to get deployed resource identifiers

2. **Test resource interactions, not just existence** - Verify IAM policies actually work by attempting operations

3. **Clean up reliably** - Always use pytest fixtures with proper teardown; use `scope="module"` to share expensive stack deployments across tests

4. **Parallel test execution** - Use `pytest-xdist` for parallel tests, but ensure stacks have unique names to avoid conflicts

5. **Meaningful assertions** - Provide clear failure messages:
   ```python
   assert timeout == 300, f"Expected visibility timeout 300, got {timeout}"
   ```

6. **Use cloud provider SDKs** - Don't just check Pulumi outputs; use boto3, azure-sdk, google-cloud to validate actual cloud state

7. **Test failure modes** - Verify that security controls prevent unauthorized access:
   ```python
   # Verify bucket blocks public access
   with pytest.raises(ClientError) as exc:
       s3.get_object(Bucket=bucket_name, Key="test")
   assert exc.value.response["Error"]["Code"] == "AccessDenied"
   ```

## Version-Specific Documentation

When referencing Pulumi AWS provider documentation:

1. **Check installed version:**
   ```bash
   pip show pulumi-aws | grep Version
   ```

2. **Reference matching documentation:**
   - **Latest docs**: https://www.pulumi.com/registry/packages/aws/api-docs/
   - **Python package docs**: https://www.pulumi.com/docs/reference/pkg/python/pulumi_aws/
   - **Version-specific PyPI**: https://pypi.org/project/pulumi-aws/{version}/

3. **Provider versioning in code:**
   ```python
   aws_provider = pulumi_aws.Provider(
       "my-provider",
       version="6.x.x",  # Pin to major version
       region="us-east-1"
   )
   ```

## Common Patterns

### Pattern: Test IAM Permissions
```python
def test_lambda_can_access_s3(pulumi_stack):
    """Verify Lambda execution role can read/write S3."""
    outputs = pulumi_stack["outputs"]
    lambda_role_arn = outputs["lambda_role_arn"].value
    bucket_name = outputs["bucket_name"].value

    # Simulate Lambda access using assume role
    sts = boto3.client("sts")
    assumed_role = sts.assume_role(
        RoleArn=lambda_role_arn,
        RoleSessionName="test-session"
    )

    # Create S3 client with assumed credentials
    s3 = boto3.client(
        "s3",
        aws_access_key_id=assumed_role["Credentials"]["AccessKeyId"],
        aws_secret_access_key=assumed_role["Credentials"]["SecretAccessKey"],
        aws_session_token=assumed_role["Credentials"]["SessionToken"]
    )

    # Verify can write
    s3.put_object(Bucket=bucket_name, Key="test.txt", Body=b"test")

    # Verify can read
    obj = s3.get_object(Bucket=bucket_name, Key="test.txt")
    assert obj["Body"].read() == b"test"
```

### Pattern: Test Network Connectivity
```python
def test_ecs_can_reach_rds(pulumi_stack):
    """Verify ECS tasks can connect to RDS in private subnet."""
    outputs = pulumi_stack["outputs"]
    cluster_name = outputs["ecs_cluster_name"].value
    rds_endpoint = outputs["rds_endpoint"].value

    ecs = boto3.client("ecs")

    # Run ephemeral task that tests DB connection
    response = ecs.run_task(
        cluster=cluster_name,
        taskDefinition="connectivity-test",
        overrides={
            "containerOverrides": [{
                "name": "tester",
                "environment": [
                    {"name": "DB_HOST", "value": rds_endpoint}
                ]
            }]
        }
    )

    # Wait for task and check exit code
    task_arn = response["tasks"][0]["taskArn"]
    waiter = ecs.get_waiter("tasks_stopped")
    waiter.wait(cluster=cluster_name, tasks=[task_arn])

    task = ecs.describe_tasks(cluster=cluster_name, tasks=[task_arn])
    exit_code = task["tasks"][0]["containers"][0]["exitCode"]
    assert exit_code == 0, "ECS task could not connect to RDS"
```

## Troubleshooting

**Issue: Tests are too slow**
- Solution: Use LocalStack for local tests, only test against real cloud in CI
- Solution: Reduce stack scope - test one module at a time
- Solution: Use `scope="session"` for shared fixtures

**Issue: Tests are flaky**
- Solution: Add retry logic for eventually-consistent resources
- Solution: Use proper waiters (e.g., `boto3.client.get_waiter()`)
- Solution: Increase timeouts for resource provisioning

**Issue: Stack destroy fails**
- Solution: Ensure all resources are properly tagged for cleanup
- Solution: Use `force=True` in destroy for stuck resources
- Solution: Add explicit dependencies so destroy order is correct

**Issue: Low coverage**
- Solution: Focus on integration tests of critical paths
- Solution: Use `--cov` to identify untested infrastructure modules
- Solution: Add property tests for security-critical configurations

## References

- Pulumi Testing Docs: https://www.pulumi.com/docs/iac/concepts/testing/
- Pulumi Automation API: https://www.pulumi.com/docs/using-pulumi/automation-api/
- Pytest Best Practices: https://docs.pytest.org/en/stable/goodpractices.html
- LocalStack Integration: https://blog.localstack.cloud/integration-testing-pulumi-localstack-automation-api/
