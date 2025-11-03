# Pulumi Testing Implementation Guide

This document compiles the relevant documentation, patterns, and examples used to implement comprehensive tests for Pulumi infrastructure code, following industry best practices and Open Policy Agent (OPA) principles.

## Table of Contents

- [Official Pulumi Testing Documentation](#official-pulumi-testing-documentation)
- [Real-World Examples](#real-world-examples)
- [Testing Patterns and Best Practices](#testing-patterns-and-best-practices)
- [Implementation Approach](#implementation-approach)
- [Mock-Based Unit Testing](#mock-based-unit-testing)
- [Property Testing with OPA](#property-testing-with-opa)
- [Integration Testing](#integration-testing)
- [Configuration Testing](#configuration-testing)
- [Security and Compliance Testing](#security-and-compliance-testing)

## Official Pulumi Testing Documentation

### Core Testing Guide

- **[Testing Pulumi Programs](https://www.pulumi.com/docs/guides/testing/)** - Comprehensive overview of testing approaches
  - Unit Testing: Fast in-memory tests with mocks
  - Property Testing: Resource-level assertions during deployment
  - Integration Testing: End-to-end validation of deployed infrastructure

### Unit Testing Documentation

- **[Unit Testing Guide](https://www.pulumi.com/docs/guides/testing/unit/)** - Detailed guide for mock-based testing
  - Mock implementation patterns
  - Test framework integration
  - Resource validation approaches

### Property Testing (Policy as Code)

- **[Property Testing Guide](https://www.pulumi.com/docs/guides/testing/property-testing/)** - Policy-based validation
  - CrossGuard/Policy as Code integration
  - Compliance validation patterns
  - Resource property assertions

### Integration Testing

- **[Integration Testing Guide](https://www.pulumi.com/docs/guides/testing/integration/)** - End-to-end testing
  - Deploy-check-destroy patterns
  - Ephemeral environment testing
  - Real infrastructure validation

## Real-World Examples

### Official Pulumi Examples Repository

- **[Testing Examples](https://github.com/pulumi/examples#testing)** - Collection of testing examples
  - **[Python Unit Tests](https://github.com/pulumi/examples/tree/master/testing-unit-py)** - Mock-based testing in Python
  - **[TypeScript Unit Tests](https://github.com/pulumi/examples/tree/master/testing-unit-ts)** - Mock-based testing in TypeScript
  - **[Property Testing (TypeScript)](https://github.com/pulumi/examples/tree/master/testing-pac-ts)** - Policy as Code examples
  - **[Integration Testing (Go)](https://github.com/pulumi/examples/tree/master/testing-integration)** - Deploy-check-destroy patterns

### Key Example Files

- **[Python Unit Test Example](https://github.com/pulumi/examples/blob/master/testing-unit-py/__main__.py)** - Main test structure
- **[Mock Implementation](https://github.com/pulumi/examples/blob/master/testing-unit-py/test_s3.py)** - Mock class implementation
- **[Resource Validation](https://github.com/pulumi/examples/blob/master/testing-unit-py/test_s3.py)** - Resource property testing

## Testing Patterns and Best Practices

### 1. Mock-Based Unit Testing (Primary Pattern)

**Documentation:**

- [Pulumi Runtime Mocks](https://www.pulumi.com/docs/reference/pkg/python/pulumi/#pulumi.runtime.Mocks)
- [Mock Resource Arguments](https://www.pulumi.com/docs/reference/pkg/python/pulumi/#pulumi.runtime.MockResourceArgs)
- [Mock Call Arguments](https://www.pulumi.com/docs/reference/pkg/python/pulumi/#pulumi.runtime.MockCallArgs)

**Pattern:**

```python
class Mocks(pulumi.runtime.Mocks):
    def new_resource(self, args: pulumi.runtime.MockResourceArgs):
        # Mock resource creation with type-specific returns
        if args.typ == "aws:sqs/queue:Queue":
            outputs = {
                **args.inputs,
                "arn": f"arn:aws:sqs:us-east-1:123456789012:{args.name}",
                "id": f"https://sqs.us-east-1.amazonaws.com/123456789012/{args.name}",
            }
            return [args.name + "_id", outputs]
        return [args.name + "_id", args.inputs]

    def call(self, args: pulumi.runtime.MockCallArgs):
        # Mock provider calls (get_* functions, data sources)
        return {}


@pytest.fixture(autouse=True)
def setup_mocks():
    pulumi.runtime.set_mocks(Mocks())
```

### 2. Test Decorators and Assertions

**Documentation:**

- [@pulumi.runtime.test](https://www.pulumi.com/docs/reference/pkg/python/pulumi/#pulumi.runtime.test)
- [Output.all() for Multiple Values](https://www.pulumi.com/docs/reference/pkg/python/pulumi/#pulumi.Output.all)

**Pattern:**

```python
@pulumi.runtime.test
def test_resource_properties():
    def check_properties(args):
        urn, resource_inputs = args
        assert resource_inputs["fifo_queue"] is True
        assert resource_inputs["visibility_timeout_seconds"] == 300

    return pulumi.Output.all(resource.urn, resource.__dict__).apply(check_properties)
```

### 3. Configuration Testing

**Documentation:**

- [Pulumi Configuration](https://www.pulumi.com/docs/concepts/config/)
- [Stack Settings](https://www.pulumi.com/docs/concepts/projects/stacks/)

**Pattern:**

```python
def test_configuration_loading():
    with patch("pulumi.Config") as mock_config_class:
        mock_config = MagicMock()
        mock_config.get_object.return_value = {
            "aws": {"region": "us-east-1"},
            "queue": {"visibilityTimeout": "300"},
        }
        mock_config_class.return_value = mock_config

        settings = StackSettings.load()
        assert settings.aws.region == "us-east-1"
        assert settings.queue.visibility_timeout == 300
```

## Implementation Approach

### Project Structure

```
deploy/
├── components/          # Reusable AWS primitives
│   ├── sqs_fifo.py
│   ├── ecs_helpers.py
│   └── ecr_repository.py
├── modules/            # Application-specific infrastructure
│   ├── dagster.py
│   └── taskiq.py
├── config.py           # Configuration loading
├── conftest.py        # Test fixtures and mocks
├── test_config.py      # Configuration tests
├── test_sqs_fifo.py   # Component tests
├── test_dagster.py    # Module tests
└── test_taskiq.py     # Module tests
```

### Test Organization Principles

1. **Component Testing**: Test reusable infrastructure components in isolation
1. **Module Testing**: Test application-specific infrastructure bundles
1. **Configuration Testing**: Validate configuration loading and defaults
1. **Security Testing**: Ensure compliance with organizational standards
1. **Integration Testing**: End-to-end validation of critical paths

## Mock-Based Unit Testing

### Mock Implementation

**Reference:** [Python Unit Testing Example](https://github.com/pulumi/examples/blob/master/testing-unit-py/test_s3.py)

```python
class Mocks(pulumi.runtime.Mocks):
    def new_resource(self, args: pulumi.runtime.MockResourceArgs):
        """Mock resource creation with type-specific behavior."""
        if args.typ == "aws:sqs/queue:Queue":
            return [
                f"{args.name}_id",
                {
                    **args.inputs,
                    "arn": f"arn:aws:sqs:us-east-1:123456789012:{args.name}",
                    "id": f"https://sqs.us-east-1.amazonaws.com/123456789012/{args.name}",
                },
            ]
        return [f"{args.name}_id", args.inputs]

    def call(self, args: pulumi.runtime.MockCallArgs):
        """Mock provider calls for data sources."""
        return {}
```

### Resource Validation Tests

**Reference:** [Resource Property Validation](https://github.com/pulumi/examples/blob/master/testing-unit-py/test_s3.py)

```python
@pulumi.runtime.test
def test_sqs_fifo_configuration():
    def check_fifo_properties(args):
        urn, queue_inputs = args
        assert queue_inputs["fifo_queue"] is True
        assert queue_inputs["content_based_deduplication"] is True
        assert queue_inputs["visibility_timeout_seconds"] == 300

    return pulumi.Output.all(queue.urn, queue.__dict__).apply(check_fifo_properties)
```

### Security Compliance Tests

**Reference:** [Security Testing Patterns](https://github.com/pulumi/examples/blob/master/testing-unit-py/test_s3.py)

```python
@pulumi.runtime.test
def test_security_group_rules():
    def check_security_group_rules(args):
        urn, ingress = args
        ssh_open = any([
            rule["from_port"] == 22 and any([block == "0.0.0.0/0" for block in rule["cidr_blocks"]]) for rule in ingress
        ])
        assert not ssh_open, f"security group {urn} exposes port 22 to Internet"

    return pulumi.Output.all(security_group.urn, security_group.ingress).apply(check_security_group_rules)
```

## Property Testing with OPA

### Policy as Code Integration

**Documentation:**

- [Pulumi Policy as Code](https://www.pulumi.com/docs/policy/)
- [Policy Packs](https://www.pulumi.com/docs/policy/policy-packs/)
- [Policy SDK](https://www.pulumi.com/docs/reference/pkg/python/pulumi_policy/)

**Example Policy Structure:**

```python
from pulumi_policy import EnforcementLevel, ResourceValidationPolicy


def sqs_fifo_policy():
    return ResourceValidationPolicy(
        name="sqs-fifo-configuration",
        description="Ensures SQS queues have proper FIFO configuration",
        enforcement=EnforcementLevel.MANDATORY,
        validate=lambda args: {
            "violations": []
            if args.props.get("fifoQueue", False)
            else [
                {
                    "msg": "SQS queue must be FIFO",
                    "extract": args.props,
                }
            ]
        },
    )
```

### Policy Testing

**Reference:** [Property Testing Examples](https://github.com/pulumi/examples/tree/master/testing-pac-ts)

```python
def test_policy_compliance():
    policy_pack = PolicyPack(
        name="compliance-pack",
        policies=[sqs_fifo_policy()],
    )

    # Test against infrastructure
    result = policy_pack.test(infrastructure)
    assert len(result.violations) == 0
```

## Integration Testing

### Deploy-Check-Destroy Pattern

**Documentation:** [Integration Testing Guide](https://www.pulumi.com/docs/guides/testing/integration/)

**Example Implementation:**

```python
def test_deployed_infrastructure():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Deploy infrastructure
        stack = auto.create_or_select_stack("test-integration", project, work_dir=temp_dir)
        stack.set_config("aws:region", auto.ConfigValue("us-east-1"))
        stack.up(on_output=print)

        # Get outputs and test
        outputs = stack.outputs()
        queue_url = outputs["queue_url"]

        # Test actual infrastructure
        response = requests.get(f"{queue_url}/health")
        assert response.status_code == 200

        # Cleanup
        stack.destroy(on_output=print)
```

## Configuration Testing

### Stack Settings Validation

**Documentation:**

- [Configuration Management](https://www.pulumi.com/docs/concepts/config/)
- [Stack Configuration](https://www.pulumi.com/docs/concepts/projects/stacks/)

**Implementation Pattern:**

```python
@patch("pulumi.Config")
def test_stack_settings_loading(mock_config_class):
    mock_config = MagicMock()
    mock_config.get_object.side_effect = lambda key: {
        "project": {"name": "test-project", "environment": "test"},
        "aws": {"region": "us-east-1", "endpoint": "http://localhost:4566"},
        "queue": {"visibilityTimeout": "300", "messageRetentionSeconds": "1209600"},
    }.get(key, {})
    mock_config_class.return_value = mock_config

    settings = StackSettings.load()
    assert settings.project.name == "test-project"
    assert settings.aws.region == "us-east-1"
    assert settings.queue.visibility_timeout == 300
```

### Parameterized Configuration Tests

**Reference:** [pytest.mark.parametrize](https://docs.pytest.org/en/stable/reference/parametrize.html)

```python
@pytest.mark.parametrize(
    "config_key,field_name,expected_value",
    [
        ("project", "name", "custom-project"),
        ("aws", "region", "eu-west-1"),
        ("queue", "messageRetentionSeconds", "864000"),
        ("database", "engineVersion", "16"),
        ("services", "daemonDesiredCount", "3"),
    ],
)
def test_individual_config_overrides(mock_config_class, config_key, field_name, expected_value):
    # Test individual configuration overrides
    pass
```

## Security and Compliance Testing

### Infrastructure Security Validation

**Documentation:**

- [Security Best Practices](https://www.pulumi.com/docs/guides/basics/iac-least-privileges/)
- [Compliance Validation](https://www.pulumi.com/docs/insights/policy/)

**Security Test Patterns:**

```python
@pulumi.runtime.test
def test_sqs_encryption():
    def check_encryption(args):
        urn, queue_props = args
        assert queue_props.get("sqsManagedSseEnabled", False), (
            f"SQS queue {urn} must have server-side encryption enabled"
        )

    return pulumi.Output.all(queue.urn, queue.__dict__).apply(check_encryption)


@pulumi.runtime.test
def test_iam_least_privilege():
    def check_iam_permissions(args):
        urn, policy_document = args
        statements = json.loads(policy_document)["Statement"]
        for statement in statements:
            if statement["Effect"] == "Allow":
                assert "*" not in statement.get("Action", []), f"IAM role {urn} should not use wildcard actions"

    return pulumi.Output.all(role.urn, role.policy).apply(check_iam_permissions)
```

### Compliance Framework Integration

**Documentation:**

- [Compliance-Ready Policies](https://www.pulumi.com/docs/insights/policy/compliance-ready-policies/)
- [AWS Guard](https://www.pulumi.com/docs/insights/policy/pre-built-packs/#awsguard)

**Implementation:**

```python
# Use existing compliance policies
from pulumi_policy_aws import AWSGuard


def test_compliance_with_aws_guard():
    policy_pack = PolicyPack(
        name="aws-compliance",
        policies=AWSGuard,
    )

    # Test infrastructure against AWS Guard policies
    result = policy_pack.test(infrastructure)
    assert len(result.violations) == 0
```

## Additional Resources

### Testing Frameworks

- **[pytest](https://docs.pytest.org/)** - Primary testing framework
- **[pytest-mock](https://pytest-mock.readthedocs.io/)** - Mocking utilities
- **[unittest.mock](https://docs.python.org/3/library/unittest.mock.html)** - Standard library mocking

### Pulumi SDK References

- **[Python SDK Reference](https://www.pulumi.com/docs/reference/pkg/python/pulumi/)**
- **[AWS Provider Reference](https://www.pulumi.com/docs/reference/pkg/python/pulumi_aws/)**
- **[Runtime API](https://www.pulumi.com/docs/reference/pkg/python/pulumi/#pulumi.runtime)**

### Community Resources

- **[Pulumi Community Slack](https://slack.pulumi.com/)** - Testing discussions
- **[GitHub Discussions](https://github.com/pulumi/pulumi/discussions)** - Testing patterns
- **[Stack Overflow](https://stackoverflow.com/questions/tagged/pulumi)** - Testing questions

## Conclusion

This implementation follows industry best practices for Pulumi testing, combining:

1. **Mock-based unit testing** for fast feedback during development
1. **Property testing** for compliance and security validation
1. **Integration testing** for end-to-end infrastructure validation
1. **Configuration testing** for proper settings management
1. **Security testing** for compliance with organizational standards

The approach is consistent with official Pulumi documentation and real-world implementations from the Pulumi examples repository, providing comprehensive coverage of infrastructure code testing needs.
