---
name: opa-testing
description: Guide for writing effective OPA (Open Policy Agent) policy tests using Rego with high coverage and best practices
allowed-tools: "Read,Write,Edit,Bash,Grep,Glob"
version: 1.0.0
---

# OPA Policy Testing with Rego

Guide for writing effective unit tests for Open Policy Agent (OPA) policies using Rego, following best practices for coverage, naming conventions, and CI/CD integration.

## Testing Philosophy

**Test-Driven Policy Development** - Write tests before policies to ensure policies behave correctly from the start. This catches edge cases early and documents expected policy behavior.

**Comprehensive Coverage** - Aim for >80% code coverage of policy rules. Use `opa test --coverage` to identify untested paths.

**Fail-Safe Defaults** - Tests should verify that policies deny by default and only allow when specific conditions are met.

## Test File Structure

### Naming Conventions

**Policy files:**
- Location: `policies/` or `rego/`
- Format: `<domain>_<purpose>.rego`
- Example: `kubernetes_admission.rego`, `aws_tagging.rego`

**Test files:**
- Location: Same directory as policy or `policies_test/`
- Format: `<policyname>_test.rego`
- Example: `kubernetes_admission_test.rego`, `aws_tagging_test.rego`

**Test rules:**
- Format: `test_<descriptive_name>`
- Example: `test_deny_privileged_containers`, `test_allow_approved_registries`

### Directory Structure
```
project/
├── policies/
│   ├── kubernetes_admission.rego
│   ├── kubernetes_admission_test.rego
│   ├── aws_tagging.rego
│   ├── aws_tagging_test.rego
│   └── data/
│       ├── approved_registries.json
│       └── required_tags.json
├── scripts/
│   └── run_policy_tests.sh
└── .opaconfiguration
```

## Basic Test Structure

### Policy Example
```rego
# policies/kubernetes_admission.rego
package kubernetes.admission

# Deny privileged containers
deny[msg] {
    input.request.kind.kind == "Pod"
    container := input.request.object.spec.containers[_]
    container.securityContext.privileged == true
    msg := sprintf("Privileged container not allowed: %s", [container.name])
}

# Deny images from unapproved registries
deny[msg] {
    input.request.kind.kind == "Pod"
    container := input.request.object.spec.containers[_]
    image := container.image
    not startswith(image, "gcr.io/approved/")
    not startswith(image, "docker.io/approved/")
    msg := sprintf("Image from unapproved registry: %s", [image])
}

# Allow if no denials
allow {
    count(deny) == 0
}
```

### Test Example
```rego
# policies/kubernetes_admission_test.rego
package kubernetes.admission

# Test: Deny privileged containers
test_deny_privileged_container {
    # Arrange: Create test input with privileged container
    input := {
        "request": {
            "kind": {"kind": "Pod"},
            "object": {
                "spec": {
                    "containers": [{
                        "name": "nginx",
                        "image": "nginx:latest",
                        "securityContext": {"privileged": true}
                    }]
                }
            }
        }
    }

    # Act: Evaluate policy
    result := deny with input as input

    # Assert: Verify denial message
    count(result) == 1
    result[_] == "Privileged container not allowed: nginx"
}

# Test: Allow non-privileged containers from approved registry
test_allow_approved_nonprivileged_container {
    input := {
        "request": {
            "kind": {"kind": "Pod"},
            "object": {
                "spec": {
                    "containers": [{
                        "name": "app",
                        "image": "gcr.io/approved/app:v1",
                        "securityContext": {"privileged": false}
                    }]
                }
            }
        }
    }

    # Should have no denials
    result := deny with input as input
    count(result) == 0

    # Should explicitly allow
    allow with input as input
}

# Test: Deny unapproved registry
test_deny_unapproved_registry {
    input := {
        "request": {
            "kind": {"kind": "Pod"},
            "object": {
                "spec": {
                    "containers": [{
                        "name": "app",
                        "image": "malicious-registry.com/app:latest"
                    }]
                }
            }
        }
    }

    result := deny with input as input
    count(result) >= 1
    result[_] == "Image from unapproved registry: malicious-registry.com/app:latest"
}

# Test: Handle multiple containers
test_deny_multiple_violations {
    input := {
        "request": {
            "kind": {"kind": "Pod"},
            "object": {
                "spec": {
                    "containers": [
                        {
                            "name": "nginx",
                            "image": "bad-registry.com/nginx:latest",
                            "securityContext": {"privileged": true}
                        },
                        {
                            "name": "sidecar",
                            "image": "bad-registry.com/sidecar:latest"
                        }
                    ]
                }
            }
        }
    }

    result := deny with input as input
    # Should have 3 violations: 1 privileged + 2 unapproved registries
    count(result) == 3
}
```

## Running Tests

### Basic Test Execution
```bash
# Run all tests in a directory
opa test policies/

# Run specific test file
opa test policies/kubernetes_admission_test.rego

# Verbose output
opa test -v policies/

# Run tests matching regex pattern
opa test --run 'test_deny_.*' policies/
```

### Coverage Reporting
```bash
# Generate coverage report
opa test --coverage policies/

# Output coverage to file
opa test --coverage --format=json policies/ > coverage.json

# Fail if coverage below threshold (requires custom script)
opa test --coverage policies/ | grep -q "100.0%" || exit 1
```

### Example Coverage Output
```
PASS: 15/15
COVERAGE: 87.5%
policies/kubernetes_admission.rego:
  kubernetes.admission.deny: 100.0%
  kubernetes.admission.allow: 100.0%
policies/aws_tagging.rego:
  aws.tagging.compliant: 75.0%  # Missing test for edge case
```

## Advanced Testing Patterns

### Pattern 1: Testing with External Data

**Policy using external data:**
```rego
# policies/aws_tagging.rego
package aws.tagging

import data.required_tags

# Check if resource has all required tags
compliant[resource_id] {
    resource := input.resources[resource_id]
    all_tags_present(resource.tags)
}

all_tags_present(tags) {
    required := required_tags
    required[_].key == tags[_].key
    # All required tags must be present
    count([tag | tag := required[_]; tags[_].key == tag.key]) == count(required)
}
```

**Test with mocked data:**
```rego
# policies/aws_tagging_test.rego
package aws.tagging

# Mock external data for testing
test_compliant_with_all_required_tags {
    # Arrange: Mock required tags data
    mock_required_tags := [
        {"key": "Environment", "values": ["prod", "dev", "staging"]},
        {"key": "Owner", "values": ["team-a", "team-b"]},
        {"key": "CostCenter", "values": ["1234", "5678"]}
    ]

    input := {
        "resources": {
            "i-1234567": {
                "type": "ec2:instance",
                "tags": [
                    {"key": "Environment", "value": "prod"},
                    {"key": "Owner", "value": "team-a"},
                    {"key": "CostCenter", "value": "1234"}
                ]
            }
        }
    }

    # Act: Evaluate with mocked data
    result := compliant with input as input with data.required_tags as mock_required_tags

    # Assert
    result["i-1234567"]
}

test_noncompliant_missing_required_tag {
    mock_required_tags := [
        {"key": "Environment"},
        {"key": "Owner"}
    ]

    input := {
        "resources": {
            "i-7654321": {
                "tags": [
                    {"key": "Environment", "value": "dev"}
                    # Missing "Owner" tag
                ]
            }
        }
    }

    result := compliant with input as input with data.required_tags as mock_required_tags

    # Should NOT be compliant
    not result["i-7654321"]
}
```

### Pattern 2: Parameterized Tests (Test Helpers)

```rego
# policies/kubernetes_rbac_test.rego
package kubernetes.rbac

# Helper function for creating RBAC test inputs
make_role_binding(namespace, role, subjects) := {
    "request": {
        "kind": {"kind": "RoleBinding"},
        "object": {
            "metadata": {"namespace": namespace},
            "roleRef": {"name": role},
            "subjects": subjects
        }
    }
}

test_deny_cluster_admin_in_default_namespace {
    input := make_role_binding(
        "default",
        "cluster-admin",
        [{"kind": "User", "name": "alice"}]
    )

    result := deny with input as input
    count(result) > 0
}

test_allow_view_role_in_default_namespace {
    input := make_role_binding(
        "default",
        "view",
        [{"kind": "User", "name": "bob"}]
    )

    result := deny with input as input
    count(result) == 0
}

# Test table pattern (using array of test cases)
test_role_permissions {
    test_cases := [
        # {description, namespace, role, should_deny}
        {"cluster-admin in default", "default", "cluster-admin", true},
        {"cluster-admin in kube-system", "kube-system", "cluster-admin", false},
        {"edit in app namespace", "app-prod", "edit", false},
        {"admin in default", "default", "admin", true}
    ]

    # All test cases should pass
    all_pass(test_cases)
}

all_pass(cases) {
    case := cases[_]
    input := make_role_binding(case[1], case[2], [{"kind": "User", "name": "test"}])
    result := deny with input as input
    case[3] == (count(result) > 0)  # should_deny matches actual result
}
```

### Pattern 3: Testing Negative Cases (Ensure Denies Work)

```rego
# Always test both positive and negative cases
test_policy_denies_when_should_deny {
    # Verify policy catches violations
    input := make_bad_input()
    result := deny with input as input
    count(result) > 0  # Must have at least one denial
}

test_policy_allows_when_should_allow {
    # Verify policy doesn't have false positives
    input := make_good_input()
    result := deny with input as input
    count(result) == 0  # Must have NO denials
}

test_default_deny {
    # Verify policy denies by default when missing data
    input := {}
    not allow with input as input
}
```

## CI/CD Integration

### GitHub Actions Example
```yaml
# .github/workflows/opa-tests.yml
name: OPA Policy Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install OPA
        run: |
          curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64
          chmod +x opa
          sudo mv opa /usr/local/bin/

      - name: Run OPA tests
        run: opa test -v --fail-on-empty policies/

      - name: Check coverage
        run: |
          opa test --coverage --format=json policies/ > coverage.json
          COVERAGE=$(jq -r '.coverage' coverage.json)
          echo "Coverage: $COVERAGE%"
          # Fail if coverage below 80%
          if (( $(echo "$COVERAGE < 80" | bc -l) )); then
            echo "Coverage below 80%!"
            exit 1
          fi

      - name: Run Regal linter
        run: |
          # Install Regal (OPA linter)
          go install github.com/StyraInc/regal@latest
          regal lint policies/
```

### GitLab CI Example
```yaml
# .gitlab-ci.yml
opa-tests:
  image: openpolicyagent/opa:latest
  stage: test
  script:
    - opa test -v --fail-on-empty policies/
    - opa test --coverage policies/ | tee coverage.txt
    - grep -q "100.0%" coverage.txt || (echo "Coverage not 100%" && exit 1)
  artifacts:
    reports:
      junit: test-results.xml
```

### Pre-commit Hook
```bash
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: opa-test
        name: OPA Policy Tests
        entry: opa test --fail-on-empty
        args: [policies/]
        language: system
        pass_filenames: false

      - id: opa-fmt
        name: OPA Format Check
        entry: opa fmt
        args: [--fail, policies/]
        language: system
        pass_filenames: false
```

## Best Practices

### 1. Descriptive Test Names

**Bad:**
```rego
test_1 { ... }
test_deny { ... }
test_check { ... }
```

**Good:**
```rego
test_deny_privileged_containers { ... }
test_allow_approved_registries { ... }
test_require_resource_limits { ... }
```

### 2. Arrange-Act-Assert Pattern

```rego
test_example {
    # Arrange: Setup test data
    input := {
        "user": "alice",
        "action": "read",
        "resource": "document-123"
    }

    # Act: Evaluate policy
    result := allow with input as input

    # Assert: Verify outcome
    result == true
}
```

### 3. Test Edge Cases

```rego
# Test empty inputs
test_deny_empty_input {
    result := deny with input as {}
    count(result) > 0  # Should deny empty input
}

# Test missing fields
test_deny_missing_required_fields {
    input := {"user": "alice"}  # Missing action and resource
    not allow with input as input
}

# Test null values
test_deny_null_values {
    input := {"user": null, "action": "read"}
    not allow with input as input
}

# Test arrays with zero/one/many elements
test_handle_empty_array { ... }
test_handle_single_item { ... }
test_handle_multiple_items { ... }
```

### 4. Use --fail-on-empty Flag

**Always use in CI/CD to catch typos:**
```bash
# Without flag: Silent failure if no tests run (due to typo)
opa test policies/  # Returns 0 even if no tests found

# With flag: Fails if no tests discovered
opa test --fail-on-empty policies/  # Returns 1 if no tests found
```

### 5. Mock External Dependencies

```rego
# Mock time for time-based policies
test_access_during_business_hours {
    mock_time := {"hour": 14, "day": "Monday"}  # 2 PM on Monday

    result := allow with input as user_request with data.current_time as mock_time

    result == true
}

test_deny_access_after_hours {
    mock_time := {"hour": 22, "day": "Monday"}  # 10 PM

    result := allow with input as user_request with data.current_time as mock_time

    result == false
}
```

### 6. Test Helpers for Readability

```rego
# Helper to create common test inputs
make_pod(name, image, privileged) := {
    "kind": "Pod",
    "metadata": {"name": name},
    "spec": {
        "containers": [{
            "name": name,
            "image": image,
            "securityContext": {"privileged": privileged}
        }]
    }
}

# Use helper in tests
test_deny_privileged {
    pod := make_pod("nginx", "nginx:latest", true)
    count(deny with input as pod) > 0
}

test_allow_nonprivileged {
    pod := make_pod("app", "gcr.io/app:v1", false)
    count(deny with input as pod) == 0
}
```

### 7. Document Test Purpose

```rego
# Test: CVE-2024-1234 - Ensure privilege escalation is blocked
test_cve_2024_1234_privilege_escalation {
    # Regression test for security vulnerability
    # See: https://nvd.nist.gov/vuln/detail/CVE-2024-1234
    input := exploit_payload()
    not allow with input as input
}
```

## Coverage Analysis

### Generate Detailed Coverage Report
```bash
# JSON format for programmatic analysis
opa test --coverage --format=json policies/ > coverage.json

# Pretty-printed format for human review
opa test --coverage --format=pretty policies/
```

### Coverage Report Structure
```json
{
  "files": {
    "policies/kubernetes_admission.rego": {
      "covered": 45,
      "not_covered": 5,
      "coverage": 90.0
    }
  },
  "coverage": 87.5
}
```

### Identify Untested Code
```bash
# Show lines not covered by tests
opa test --coverage policies/ | grep "not covered"

# Generate HTML coverage report (requires custom tool)
opa test --coverage --format=json policies/ | coverage-to-html > coverage.html
```

## Troubleshooting

### Issue: Tests pass but policy doesn't work in production

**Solution:** Ensure test inputs match real-world inputs exactly
```rego
# Capture real input from production
# kubectl get pod nginx -o json > test-data/real-pod.json

test_with_real_input {
    input := json.unmarshal(file.read("test-data/real-pod.json"))
    # Test against actual structure
}
```

### Issue: Tests are too slow

**Solution:** Split into smaller test files and run in parallel
```bash
# Run tests in parallel (requires GNU parallel)
find policies/ -name "*_test.rego" | parallel -j 4 opa test {}
```

### Issue: Coverage not 100% but can't identify missing tests

**Solution:** Use coverage report to find untested lines
```bash
opa test --coverage --format=json policies/ | jq '.files[] | select(.coverage < 100)'
```

### Issue: Test passes locally but fails in CI

**Solution:** Ensure OPA versions match
```bash
# Pin OPA version in CI
- name: Install OPA
  run: |
    OPA_VERSION=0.58.0
    curl -L -o opa https://openpolicyagent.org/downloads/v${OPA_VERSION}/opa_linux_amd64
```

## Integration with Pulumi CrossGuard

When using OPA policies with Pulumi:

```typescript
// Pulumi CrossGuard policy pack using OPA
import * as policy from "@pulumi/policy";

const policyPack = new policy.PolicyPack("aws-opa-policies", {
    policies: [
        {
            name: "aws-tagging-policy",
            description: "Enforce AWS tagging requirements",
            enforcementLevel: "mandatory",
            validateResource: async (args, reportViolation) => {
                // Convert Pulumi resource to OPA input format
                const opaInput = {
                    resources: {
                        [args.name]: {
                            type: args.type,
                            tags: args.props.tags
                        }
                    }
                };

                // Evaluate OPA policy
                const result = await evaluateOpaPolicy("aws.tagging", opaInput);

                if (!result.compliant) {
                    reportViolation("Resource missing required tags");
                }
            }
        }
    ]
});
```

**Test OPA policies before integrating with Pulumi:**
```bash
# 1. Test OPA policy standalone
opa test policies/aws_tagging_test.rego

# 2. Test with sample Pulumi resource
echo '{"resources": {"test-instance": {"type": "aws:ec2/instance:Instance", "tags": {}}}}' | \
    opa eval --data policies/aws_tagging.rego --input - 'data.aws.tagging.compliant'

# 3. Run Pulumi policy pack tests
cd policy-pack && npm test
```

## References

- OPA Testing Documentation: https://www.openpolicyagent.org/docs/latest/policy-testing/
- Rego Testing Best Practices: https://www.styra.com/blog/rego-unit-testing/
- Advanced Testing Techniques: https://www.styra.com/blog/advanced-rego-testing-techniques/
- Regal Linter: https://github.com/StyraInc/regal
- OPA Coverage: https://www.openpolicyagent.org/docs/latest/policy-testing/#coverage
