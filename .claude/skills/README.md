# Claude Skills for Infrastructure Development

This directory contains Claude Skills that provide specialized guidance for infrastructure development, testing, and best practices.

## Available Skills

### 1. `pulumi-testing` - Pulumi Infrastructure Testing

**Invoke with:** `/pulumi-testing` (when using Claude Code)

**Purpose:** Comprehensive guide for writing effective Pulumi infrastructure tests using pytest with minimal mocking and high coverage (>80%).

**Key Topics:**
- Integration testing with Automation API
- Ephemeral stack testing patterns
- Pytest fixtures for stack lifecycle management
- LocalStack integration for cost-effective testing
- Property tests vs unit tests
- Coverage strategy for infrastructure
- Version-specific documentation references

**When to use:**
- Writing tests for Pulumi infrastructure code
- Setting up CI/CD testing pipelines
- Implementing test-driven infrastructure development
- Troubleshooting failing infrastructure tests

**Philosophy:** Prefer integration tests over unit tests. Focus on the fewest tests that reach >80% coverage at a high level with minimal mocking.

---

### 2. `opa-testing` - OPA Policy Testing

**Invoke with:** `/opa-testing` (when using Claude Code)

**Purpose:** Guide for writing effective unit tests for Open Policy Agent (OPA) policies using Rego, following best practices for coverage, naming conventions, and CI/CD integration.

**Key Topics:**
- Rego test structure and naming conventions
- Test-driven policy development
- Coverage reporting with `opa test --coverage`
- CI/CD integration (GitHub Actions, GitLab CI)
- Advanced testing patterns (mocking, parameterized tests)
- Testing with external data
- Integration with Pulumi CrossGuard

**When to use:**
- Writing OPA policies for infrastructure validation
- Testing Kubernetes admission policies
- Implementing policy as code for AWS/Azure/GCP
- Setting up automated policy testing in CI/CD

**Philosophy:** Aim for >80% code coverage. Test both positive and negative cases. Fail-safe defaults (deny by default, allow only when specific conditions are met).

---

### 3. `aws-pulumi-best-practices` - AWS Pulumi Best Practices

**Invoke with:** `/aws-pulumi-best-practices` (when using Claude Code)

**Purpose:** Comprehensive guide for building secure, maintainable, and cost-effective AWS infrastructure using Pulumi, with emphasis on policy enforcement, resource tagging, security best practices, and navigating version-specific documentation.

**Key Topics:**
- Finding version-specific Pulumi AWS documentation
- Resource tagging strategies (AWS Organizations Tag Policies)
- Security best practices (IAM, encryption, secrets management, network security)
- Policy as Code with CrossGuard
- Cost optimization techniques
- Monitoring and observability
- Infrastructure organization patterns
- Common anti-patterns to avoid

**When to use:**
- Building new AWS infrastructure with Pulumi
- Implementing security and compliance requirements
- Setting up tagging and cost allocation
- Troubleshooting Pulumi AWS provider issues
- Finding correct documentation for specific provider versions

**Philosophy:** Security by default. Use managed services and policies. Tag everything. Encrypt everything. Principle of least privilege.

---

## Using Skills

### In Claude Code

Skills are automatically available when using Claude Code. To invoke a skill, simply type the skill name with a forward slash:

```
/pulumi-testing
```

Claude will load the skill and apply its guidance to your current context.

### Skill Structure

Each skill is a directory containing:
- `SKILL.md` - The skill definition with YAML frontmatter and markdown content
- Additional resources (scripts, references, assets) as needed

### Skill Permissions

Skills have restricted tool access for security. Each skill declares which tools it needs:

- `pulumi-testing`: Read, Write, Edit, Bash, Grep, Glob
- `opa-testing`: Read, Write, Edit, Bash, Grep, Glob
- `aws-pulumi-best-practices`: Read, Write, Edit, Bash, Grep, Glob, WebFetch

## Development Workflow Examples

### Example 1: Testing Pulumi Infrastructure

```bash
# 1. Invoke skill
/pulumi-testing

# 2. Ask Claude to help write tests
"Write integration tests for my VPC infrastructure in infra/networking.py"

# 3. Claude will use the skill's patterns to create:
# - Pytest fixtures with stack lifecycle
# - Integration tests using Automation API
# - Proper cleanup and teardown
```

### Example 2: Implementing OPA Policies

```bash
# 1. Invoke skill
/opa-testing

# 2. Ask Claude to write policy tests
"Write OPA tests for Kubernetes admission policy that denies privileged containers"

# 3. Claude will create:
# - Properly structured test files
# - Comprehensive test coverage
# - CI/CD integration examples
```

### Example 3: AWS Resource Security

```bash
# 1. Invoke skill
/aws-pulumi-best-practices

# 2. Ask Claude for security improvements
"Review my S3 bucket configuration and apply security best practices"

# 3. Claude will:
# - Add encryption at rest
# - Configure public access blocks
# - Add proper IAM policies
# - Implement tagging strategy
```

## Combining Skills

You can combine multiple skills for comprehensive guidance:

```bash
# 1. Build AWS infrastructure with best practices
/aws-pulumi-best-practices
"Create an ECS cluster with RDS database following security best practices"

# 2. Add policy validation
/opa-testing
"Create OPA policies to validate my ECS and RDS resources"

# 3. Write tests
/pulumi-testing
"Write comprehensive tests for the infrastructure and policies"
```

## Updating Skills

Skills are versioned and can be updated independently. Check the `version` field in each `SKILL.md` frontmatter:

```yaml
---
name: pulumi-testing
version: 1.0.0
---
```

To update a skill, modify its `SKILL.md` file and increment the version number.

## Best Practices for Skill Usage

1. **Invoke skills at the start of a task** - Skills provide context that helps Claude understand your requirements better

2. **Be specific about your use case** - Skills contain comprehensive information; tell Claude what specific aspect you need

3. **Combine with local context** - Skills work best when combined with your actual code. Point Claude to relevant files

4. **Iterate with skills active** - Keep the skill active throughout your work session for consistent guidance

## Contributing

To add new skills:

1. Create a new directory in `.claude/skills/`
2. Add a `SKILL.md` file with proper frontmatter
3. Document the skill in this README
4. Test the skill with common use cases

## References

- **Claude Skills Documentation**: https://docs.claude.com/en/docs/claude-code/skills
- **Skill Authoring Best Practices**: https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices
- **Claude Skills Deep Dive**: https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/
