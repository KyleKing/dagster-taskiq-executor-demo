# Pulumi Infrastructure Tests

Comprehensive test suite for Dagster + TaskIQ infrastructure following best practices from Claude Skills for Pulumi testing, OPA testing, and AWS best practices.

## Testing Philosophy

Following the **pulumi-testing** skill guidance:
- **70% Integration Tests**: Real infrastructure deployed to LocalStack
- **20% Property Tests**: Deployment-time validation
- **10% Unit Tests**: Mocking only when necessary

**Key principle**: Fewest tests that reach >80% coverage with minimal mocking.

## Quick Start

```bash
# 1. Start LocalStack
mise run localstack:start

# 2. Run all tests
mise run test:all

# 3. Check coverage
mise run test:coverage
```

## Test Structure

```
tests/
├── integration/          # Integration tests (70% of effort)
│   ├── conftest.py                          # Automation API fixtures
│   ├── test_infrastructure_deployment.py    # Resource creation tests
│   ├── test_cross_resource_interactions.py  # IAM, networking, etc.
│   └── test_security_configurations.py      # Security validation
│
├── policies/             # OPA policies and tests
│   ├── infrastructure_security.rego         # Security policies
│   └── infrastructure_security_test.rego    # Policy tests (>80% coverage)
│
├── conftest.py           # Shared fixtures (mocking-based)
└── test_*.py             # Unit tests (minimal, only where needed)
```

## Integration Tests

### What They Test

1. **Resource Creation** (`test_infrastructure_deployment.py`)
   - Stack deploys successfully
   - All required resources exist
   - Resources have correct configurations

2. **Cross-Resource Interactions** (`test_cross_resource_interactions.py`)
   - SQS message workflow (send, receive, delete)
   - DLQ redrive policy
   - VPC subnet high-availability
   - Security group network access
   - ECS services running
   - Service discovery

3. **Security Configurations** (`test_security_configurations.py`)
   - Database encryption at rest
   - IAM least privilege
   - Security group restrictions
   - Backup retention
   - Network isolation
   - CloudWatch logs retention

### How They Work

Integration tests use **Pulumi Automation API** to:
1. Create ephemeral test stack
2. Deploy infrastructure to LocalStack
3. Validate using boto3 (not mocks!)
4. Destroy infrastructure
5. Clean up stack

**Example:**
```python
@pytest.mark.integration
def test_sqs_message_workflow(boto3_clients, stack_outputs):
    """Test actual SQS operations against deployed infrastructure."""
    sqs = boto3_clients["sqs"]
    queue_url = stack_outputs["queue_url"]

    # Send real message
    sqs.send_message(QueueUrl=queue_url, MessageBody="test")

    # Receive real message
    response = sqs.receive_message(QueueUrl=queue_url)

    # Validate
    assert len(response["Messages"]) == 1
```

## OPA Policy Tests

### Policies Enforced

From `infrastructure_security.rego`:

**Database Security:**
- ✅ Encryption at rest required
- ✅ Deletion protection in production
- ✅ Backup retention >= 7 days
- ✅ No public access in production

**Queue Security:**
- ✅ FIFO queues required
- ✅ Message retention >= 1 day
- ✅ Dead-letter queue required

**IAM Security:**
- ✅ No wildcard principals
- ✅ No full access policies (*:*)

**Network Security:**
- ✅ No unrestricted port ranges
- ✅ No sensitive ports from internet
- ✅ No SSH from 0.0.0.0/0

**ECS Security:**
- ✅ No privileged containers
- ✅ No public IPs in production

**Resource Tagging:**
- ✅ Required tags: Environment, Project, ManagedBy

**High Availability:**
- ✅ >= 2 instances in production (except singletons)

### Running OPA Tests

```bash
# Run all policy tests
mise run test:opa

# Check coverage
opa test --coverage tests/policies/

# Run specific test
opa test tests/policies/ --run test_deny_unencrypted_rds_cluster
```

**Example policy test:**
```rego
test_deny_unencrypted_rds_cluster if {
    # Arrange: Input with unencrypted database
    input := {
        "resources": [{
            "type": "aws:rds/cluster:Cluster",
            "properties": {"storageEncrypted": false}
        }]
    }

    # Act: Evaluate policy
    result := deny with input as input

    # Assert: Should deny
    count(result) > 0
}
```

## LocalStack State Management

### The Problem

**LocalStack** (Docker container) is **ephemeral**.
**Pulumi state** (on laptop) is **persistent**.

This causes state divergence when LocalStack restarts.

### Solution: Workflow Scripts

Located in `scripts/`:

1. **`localstack-dev.sh`** - Main workflow script
2. **`sync-localstack-state.py`** - Advanced state sync
3. **`pytest_localstack_sync.py`** - Automatic pytest fixtures

**Common commands:**
```bash
# Check status
./scripts/localstack-dev.sh status

# Start LocalStack
./scripts/localstack-dev.sh start

# Sync state after restart
./scripts/localstack-dev.sh restart
./scripts/localstack-dev.sh sync

# Check for divergence
./scripts/localstack-dev.sh check

# Backup state before risky changes
./scripts/localstack-dev.sh backup

# Nuclear option: reset everything
./scripts/localstack-dev.sh fresh-start
```

### Common Scenarios

**Scenario 1: LocalStack container restarted**
```bash
$ pulumi up
Error: reading S3 Bucket (my-bucket): NotFound: Not Found

# Solution:
$ mise run localstack:sync
$ pulumi up  # Now works
```

**Scenario 2: State completely corrupted**
```bash
$ mise run localstack:reset  # Destroys everything and redeploys
```

**Scenario 3: Want fresh start for testing**
```bash
$ mise run localstack:reset
$ mise run test:integration
```

## Mise Tasks

### LocalStack Management
- `mise run localstack:start` - Start LocalStack container
- `mise run localstack:sync` - Sync Pulumi state with LocalStack
- `mise run localstack:reset` - Nuclear option: destroy everything
- `mise run localstack:status` - Show status

### Testing
- `mise run test:unit` - Unit tests (fast, mocked)
- `mise run test:integration` - Integration tests (deploy to LocalStack)
- `mise run test:opa` - OPA policy tests
- `mise run test:all` - All tests
- `mise run test:coverage` - Tests with coverage report

### Development
- `mise run clean` - Remove test artifacts
- `mise run deploy:local` - Deploy to LocalStack
- `mise run destroy:local` - Destroy infrastructure

### CI/CD
- `mise run ci:test` - Full CI test suite
- `mise run ci:validate` - Validate policies and preview

## Running Tests

### Local Development

```bash
# Quick feedback - unit tests only
mise run test:unit

# Full integration tests
mise run localstack:start
mise run test:integration

# Check OPA policies
mise run test:opa

# Everything
mise run test:all
```

### With Coverage

```bash
mise run test:coverage

# View HTML report
open htmlcov/index.html
```

### Specific Test Files

```bash
# Specific test file
pytest tests/integration/test_infrastructure_deployment.py -v

# Specific test function
pytest tests/integration/test_infrastructure_deployment.py::test_sqs_queues_exist -v

# Tests matching pattern
pytest tests/integration/ -k "security" -v
```

### Test Markers

```bash
# Only integration tests
pytest -m integration

# Exclude slow tests
pytest -m "not slow"

# Only tests requiring fresh state
pytest -m fresh_state

# Multiple markers
pytest -m "integration and not slow"
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Infrastructure Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Start LocalStack
        run: mise run localstack:start

      - name: Run OPA tests
        run: mise run test:opa

      - name: Run integration tests
        run: mise run test:integration

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

## Troubleshooting

### Tests Failing with "NotFound" Errors

**Cause**: Pulumi state diverged from LocalStack reality.

**Solution**:
```bash
mise run localstack:sync
```

### Tests Are Slow

**Solutions**:
1. Run only fast tests: `pytest -m "not slow"`
2. Use LocalStack instead of real AWS
3. Reduce stack scope for faster deployment
4. Use `scope="session"` fixtures (already configured)

### Stack Deploy Fails

**Solutions**:
```bash
# Check LocalStack is running
mise run localstack:status

# Try refreshing state
mise run localstack:sync

# Nuclear option
mise run localstack:reset
```

### OPA Tests Failing

**Check OPA is installed**:
```bash
which opa
opa version

# Install if missing:
curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64
chmod +x opa
sudo mv opa /usr/local/bin/
```

## Best Practices

### From pulumi-testing Skill

1. **Prefer integration tests** - Test real infrastructure over mocks
2. **Minimal mocking** - Only mock external dependencies you can't control
3. **High-level coverage** - Test critical paths, not every property
4. **Use LocalStack** - Cost-effective testing without AWS bills
5. **State sync** - Always sync before deploying

### From opa-testing Skill

1. **Test both allow and deny** - Verify policies catch violations AND allow valid configs
2. **Descriptive names** - `test_deny_unencrypted_database` not `test_1`
3. **>80% coverage** - Use `opa test --coverage`
4. **Fail-safe defaults** - Deny by default, allow only when conditions met

### From aws-pulumi-best-practices Skill

1. **Security by default** - Encryption, least privilege, private by default
2. **Tag everything** - Required tags enforced by OPA
3. **High availability** - Multiple AZs, >= 2 instances in production
4. **Backup and retention** - >= 7 days for production

## Coverage Goals

- **Integration tests**: >80% of critical infrastructure paths
- **OPA policies**: 100% coverage of security requirements
- **Unit tests**: Only where mocking necessary

**Current coverage**:
```bash
mise run test:coverage
# View report in htmlcov/index.html
```

## Contributing

When adding new infrastructure:

1. **Add integration test** - Test the deployed resource
2. **Add OPA policy** - Enforce security/compliance
3. **Add policy test** - Test both allow and deny cases
4. **Update mise.toml** - Add mise tasks if new test category needed
5. **Run full suite** - `mise run test:all`

## References

- **pulumi-testing skill**: `.claude/skills/pulumi-testing/SKILL.md`
- **opa-testing skill**: `.claude/skills/opa-testing/SKILL.md`
- **aws-pulumi-best-practices skill**: `.claude/skills/aws-pulumi-best-practices/SKILL.md`
- **LocalStack utilities**: `scripts/`
- **Pulumi Testing Docs**: https://www.pulumi.com/docs/iac/concepts/testing/
- **OPA Testing Docs**: https://www.openpolicyagent.org/docs/policy-testing/
