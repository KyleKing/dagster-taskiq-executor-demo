# Developer Guide

Development tooling, workflows, and best practices for this monorepo.

## Project Overview

This monorepo provides a TaskIQ-based executor for Dagster using AWS SQS for distributed task execution.

## Prerequisites

```bash
# mise - Tool version management
brew install mise

# Docker Desktop or compatible Docker engine
# https://www.docker.com/products/docker-desktop/

# Initial setup
mise install
mise run env-setup
```

## Project Structure

```
dagster-taskiq/       # Core TaskIQ executor for Dagster
dagster-taskiq-demo/  # Full demo application
deploy/               # Pulumi infrastructure code
scripts/              # Build and deployment scripts
mise.toml             # Root monorepo tasks
tasks.toml            # Shared tasks for all projects
hk.pkl                # Git hooks configuration
docker-bake.hcl       # Docker build configuration
```

## Development Workflows

### Initial Setup

```bash
mise run env-setup
cd deploy && uv sync --all-groups
```

### Daily Development

```bash
# Run checks for specific project
cd dagster-taskiq
mise run :checks

# Or run across all projects
mise run //...:checks

# Auto-fix formatting issues
mise run //...:fixes
```

## Development Tools

### mise - Tool Version Management

[mise](https://mise.jdx.dev) manages tool versions and project tasks.

```bash
mise install           # Install all tools
mise tasks             # List available tasks
mise run :test         # Run task in current directory
mise run //...:test    # Run across all projects
mise run mise:bump     # Update all tool versions
```

### hk - Git Hooks Manager

[hk](https://hk.jdx.dev) manages git hooks.

```bash
hk install --mise      # Install git hooks
hk run pre-commit      # Run pre-commit checks
hk run pre-commit --fix # Run with auto-fix
```

### uv - Python Package Manager

[uv](https://docs.astral.sh/uv) is a fast Python package manager.

```bash
uv sync --all-groups   # Install dependencies
uv add <package>       # Add a dependency
uv run pytest          # Run command in venv
```

## Code Quality

```bash
cd <project>
mise run :format       # Format code
mise run :lint --fix   # Lint and fix
mise run :pyright      # Type check
mise run :mypy         # Type check
mise run :checks       # All checks
mise run :fixes        # All fixes
```

## Testing

### Running Tests

```bash
cd <project>
mise run :test
mise run :test -- -v -k "test_name"
mise run :test -- -x  # Stop on first failure
```

### Test Standards

- No unittest classes - use plain functions with pytest
- Follow AAA pattern - Arrange, Act, Assert
- Use `@pytest.mark.parametrize` for multiple cases

### Manual Testing

See [TESTING.md](TESTING.md) for comprehensive procedures.

## Shared Task Configuration

The `tasks.toml` file defines common tasks:

- `install` - Install dependencies
- `format` - Format code
- `lint` - Lint code
- `mypy` / `pyright` - Type checking
- `test` - Run tests
- `checks` - All checks
- `fixes` - All fixes

## Troubleshooting

**Pulumi locks stuck:**

```bash
cd deploy && pulumi cancel
```

**Git hooks not working:**

```bash
hk install --mise
```

**mise not finding tasks:**

```bash
echo $MISE_EXPERIMENTAL  # Should be: 1
mise doctor
mise tasks --all
```

## Documentation

- [README.md](README.md) - Project overview
- [TESTING.md](TESTING.md) - Testing procedures
- [dagster-taskiq/README.md](dagster-taskiq/README.md) - Executor docs
- [deploy/README.md](deploy/README.md) - Infrastructure docs
