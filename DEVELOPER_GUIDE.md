# Developer Guide

This guide covers the development tooling, workflows, and best practices for working with this monorepo.

## Project Overview

This monorepo demonstrates a TaskIQ-based executor for Dagster, providing an alternative to dagster-celery with improved performance. The project uses LocalStack and Pulumi for local AWS infrastructure simulation.

## Prerequisites

Install the following tools:

```bash
# mise - Tool version management
brew install mise

# Docker Desktop or compatible Docker engine
# Download from: https://www.docker.com/products/docker-desktop/

# Initial setup
mise install
mise run env-setup
```

You'll also need:

- **LocalStack Pro API key** (`LOCALSTACK_AUTH_TOKEN`) for ECS, RDS, Cloud Map, ALB support
- Edit `.env` with your LocalStack Pro token after running `env-setup`

## Development Workflows

### Initial Setup

```bash
# Install all project dependencies
mise run //...:install

# Install git hooks
hk install --mise

# Start LocalStack
pitchfork start localstack
# Or: mise run localstack:start

# Deploy infrastructure
cd deploy
mise run pulumi:up
```

### Daily Development

```bash
# Start your day
pitchfork start localstack

# Make code changes...

# Run checks and tests for specific project
cd dagster-taskiq
mise run checks

# Or run across all projects
mise run //...:checks

# Auto-fix formatting issues
mise run //...:fixes

# Build and push new images
./scripts/build-and-push.sh

# Update infrastructure if needed
cd deploy
mise run pulumi:up
```

## Development Tools

### mise - Tool Version Management

[mise](https://mise.jdx.dev) manages tool versions and project tasks. It's a modern replacement for tools like asdf, nvm, and pyenv.

- **Tool Management:**

  - Automatically installs and switches between tool versions based on project configuration
  - Configured in `mise.toml` files throughout the monorepo

- **Task Management:**

  - Common Commands:

    ```bash
    # Install all tools defined in mise.toml
    mise install
    # List all available tasks
    mise tasks ls
    # List all tasks across the monorepo
    mise tasks --all
    # Show task details
    mise task info <task-name>

    # Update all tools to latest versions
    mise run mise:bump
    ```

- This project uses mise's experimental [monorepo task mode](https://mise.jdx.dev/tasks/monorepo.html)

  ```bash
  # Run task for current directory
  cd <project-dir> && mise run :<task>
  # Or from any location within the project for specific project dir's:
  mise run //dagster-taskiq:test
  # Or all project directories
  mise run //...:test
  # The `//...:*` syntax automatically discovers all subdirectories with matching tasks and runs them in parallel where possible.
  ```

### hk - Git Hooks Manager

[hk](https://hk.jdx.dev) is a modern git hooks manager that replaces tools like pre-commit/prek and lefthook. It's configured using the Apple [pkl](https://pkl-lang.org/) configuration language.

- **Initialization**:

  ```bash
  # Install git hooks (uses mise-managed tools)
  hk install --mise

  hk uninstall # Remove hk
  ```

- **Usage**:

  ```bash
  # Run pre-commit checks manually
  hk run pre-commit

  # Run pre-push checks manually
  hk run pre-push

  # Run specific step(s)
  hk run pre-commit --step=pyright:dagster-taskiq --step=pyright:dagster-taskiq

  # Run on all files (not just staged)
  hk run pre-commit --all

  # Run with auto-fix
  hk run pre-commit --fix

  # Run from specific git ref
  hk run pre-push --from-ref=main

  # Skip hooks for a commit
  git commit --no-verify
  # Or set environment variable
  HK=0 git commit -m "message"
  ```

### pitchfork - Daemon Manager

[pitchfork](https://pitchfork.jdx.dev) manages background services and daemons for development. Currently used for Docker Compose (LocalStack).

- **Configuration** in `pitchfork.toml`

- **Usage**:

  ```bash
  # Start all daemons
  pitchfork start --all

  # Start specific daemon
  pitchfork start localstack

  # View logs
  pitchfork logs --tail

  # Stop daemon
  pitchfork stop localstack

  # Clean up all daemons
  pitchfork clean
  ```

### uv - Python Package Manager

[uv](https://docs.astral.sh/uv) is a fast Python package and project manager, replacing pip, virtualenv, poetry, etc.

- **Common Commands**:

  ```bash
  # Install dependencies and all groups (from pyproject.toml)
  uv sync --all-groups
  # Add a dependency and optionally specify a group (or extra)
  uv add <package> --group=<group>

  # Run a command in the virtual environment
  uv run pytest

  # Run a script
  uv run python script.py
  ```

## LocalStack (Pro) Setup

LocalStack provides a local AWS cloud stack for development and testing.

### Starting LocalStack

```bash
# Option 1: Use pitchfork (background daemon)
pitchfork start localstack

# Option 2: Use mise (foreground or background)
mise run //:localstack:start          # Foreground
mise run //:localstack:start --detach # Foreground

mise run //:localstack:status   # Check status
mise run //:localstack:logs     # View logs
```

### Accessing LocalStack

- **Dashboard**: <https://app.localstack.cloud>
- **Endpoint**: <https://localhost.localstack.cloud:4566> ([resolves to `127.0.0.1`](https://blog.localstack.cloud/2024-03-04-making-connecting-to-localstack-easier/))
- **AWS CLI**: Use `awslocal` instead of `aws` (automatically configured for LocalStack)

### LocalStack Commands

```bash
# AWS service queries
mise run //:aws:clusters # List ECS clusters
mise run //:aws:services # List ECS services
mise run //:aws:tasks    # List running ECS tasks
mise run //:aws:queues   # List SQS queues
mise run //:aws:images   # List ECR images

# ECS monitoring
mise run //:ecs:status SERVICE_NAME=dagster-daemon
mise run //:ecs:status SERVICE_NAME=taskiq-worker

# Log streaming (CloudWatch)
mise run //:logs:dagster-daemon
mise run //:logs:dagster-webserver
mise run //:logs:taskiq-worker
mise run //:logs:auto-scaler

# Queue monitoring (requires environment variable QUEUE_URL)
mise run //:queue:depth
```

### Infrastructure Deployment

```bash
# Deploy all infrastructure with Pulumi
mise run //deploy:pulumi:up
# Preview changes
mise run //deploy:pulumi:preview
# Destroy infrastructure
mise run //deploy:pulumi:destroy
```

### Working with Docker Images

```bash
# Build images
mise run //:build:dagster-taskiq-demo
mise run //:build:taskiq-demo

# Build and push to LocalStack ECR
./scripts/build-and-push.sh

# Check images in ECR
mise run aws:images
```

### Code Quality

```bash
# Format code
cd <project>
mise run format

# Lint code
cd <project>
mise run lint --fix

# Type check
cd <project>
mise run pyright
cd <project>
mise run mypy

# Run all checks (lint + typecheck + test)
cd <project>
mise run checks

# Run all fixes (format + lint fix)
cd <project>
mise run fixes

# Or run across all projects
mise run //...:checks
mise run //...:fixes
```

### Testing

See [Testing](#testing) section below.

### Cleanup

```bash
# Stop services
cd deploy
mise run pulumi:destroy

# Stop LocalStack
pitchfork stop localstack
# Or: mise run localstack:stop
```

## Project Structure

```
.
├── dagster-taskiq/          # Core TaskIQ executor for Dagster
│   ├── example/             # Example usage of the executor
│   └── mise.toml            # Project tasks
├── dagster-taskiq-demo/     # Full demo application
│   └── mise.toml
├── deploy/                  # Pulumi infrastructure code
│   ├── components/          # Reusable AWS primitives
│   ├── modules/             # App-specific bundles
│   └── mise.toml
├── taskiq-demo/             # Standalone TaskIQ + FastAPI demo (optional)
│   └── mise.toml
├── scripts/                 # Build and deployment scripts
├── mise.toml                # Root monorepo tasks
├── tasks.toml               # Shared tasks for all projects
├── hk.pkl                   # Git hooks configuration
├── pitchfork.toml           # Daemon configuration
└── docker-bake.hcl          # Docker build configuration
```

**Note:** The main three subprojects are `dagster-taskiq`, `dagster-taskiq-demo`, and `deploy`. These are the focus of development and have consistent formatter/checker configurations.

### Python Packages

Each Python package has:

- `pyproject.toml` - Dependencies and project metadata
- `uv.lock` - Locked dependency versions
- `mise.toml` - Task configuration (includes `../tasks.toml`)
- `tests/` - Test files

### Shared Task Configuration

The `tasks.toml` file defines common tasks used by all projects:

- `install` - Install dependencies with `uv sync --all-groups`
- `format` - Format code with ruff
- `lint` - Lint code with ruff
- `lint:power-fix` - Auto-fix with unsafe fixes
- `mypy` - Run mypy type checker
- `pyright` - Run pyright type checker
- `test` - Run tests with pytest
- `checks` - Run all checks (lint + typecheck + test)
- `fixes` - Run all fixes (format + lint fix)

## Testing

### Running Tests

```bash
# Single project
cd <project>
mise run test

# All projects
mise run //...:test

# Specific test file
cd <project>
mise run test -- tests/test_specific.py

# Specific test function
cd <project>
mise run test -- -k "test_function_name"

# Verbose output
cd <project>
mise run test -- -v

# Stop on first failure
cd <project>
mise run test -- -x
```

### Test Standards

- **No unittest classes** - Use plain functions with pytest
- **Follow AAA pattern** - Arrange, Act, Assert
- **Test at interface level** - Test Dagster jobs, not internal implementation
- **Use modern APIs** - Use `execute_in_process()` for Dagster testing
- **Parametrize** - Use `@pytest.mark.parametrize` for multiple cases

### Manual Testing

For comprehensive manual testing procedures, see [TESTING.md](TESTING.md).

Quick workflow:

1. Start LocalStack: `mise run localstack:start`
1. Deploy infrastructure: `mise run //deploy:pulumi:up`
1. Submit job via Dagster UI (<https://TBD>)
1. Monitor: `mise run //:queue:depth` (<https://github.com/dhth/cueitup>)
1. Watch logs: `mise run logs:taskiq-worker`

<!-- TODO: Revisit guidance above -->

## Troubleshooting

### Common Issues

**Pulumi locks stuck:**

```bash
cd deploy
pulumi cancel
```

**LocalStack not responding:**

```bash
mise run //:localstack:restart
```

**Queue not processing:**

```bash
# Check worker service
mise run //:ecs:status SERVICE_NAME=taskiq-worker

# Check worker logs
mise run //:logs:taskiq-worker

# Check queue depth
mise run //:queue:depth
```

**Git hooks not working:**

```bash
# Reinstall hooks
hk install --mise

# Check config path (https://github.com/jdx/hk/discussions/385)
git config --global core.hooksPath
git config core.hooksPath
# git config --unset core.hooksPath
```

**mise not finding tasks:**

```bash
# Make sure MISE_EXPERIMENTAL is set
echo $MISE_EXPERIMENTAL # Should output: 1

# Reload mise configuration
mise doctor

# Check task list
mise tasks --all
```

### Project-Specific Docs

- [README.md](README.md) - Project overview and quick start
- [TESTING.md](TESTING.md) - Comprehensive testing procedures
- [AGENTS.md](AGENTS.md) - Quick reference for AI coding assistants
- [dagster-taskiq/README.md](dagster-taskiq/README.md) - Executor documentation
- [deploy/README.md](deploy/README.md) - Infrastructure documentation
