# Dagster TaskIQ LocalStack Demo

## Project Overview

This project demonstrates a production-like AWS deployment of Dagster with TaskIQ execution running locally using LocalStack. It showcases distributed job execution, auto-scaling, failure recovery, and exactly-once execution semantics.

## Architecture Components

- **Dagster**: Orchestration platform with daemon and web UI
- **TaskIQ**: Distributed task execution framework
- **LocalStack**: Local AWS service emulation (SQS, ECS, EC2, RDS)
- **PostgreSQL**: Database backend for Dagster metadata and state
- **Auto-scaler**: Dynamic worker scaling based on queue depth
- **Load Simulator**: Testing framework for various load scenarios

## Key Features

- Implemented according to documentation in `.kiro/specs/dagster-taskiq-localstack/*.md`
    - Exactly-once execution guarantees
    - Automatic scaling based on queue depth
    - Failure simulation and recovery testing
    - Mixed workload support (fast/slow jobs)
    - Infrastructure as code with Pulumi
    - Comprehensive monitoring and metrics

## Development Setup

The project uses:
- `uv` for Python package management
- `mise` (jdx/mise) for tool version management
- Docker Compose for LocalStack orchestration
- Pulumi for infrastructure provisioning

## Project Structure

```
./
├── app/                    # Main Python application
│   ├── src/
│   │   ├── dagster_jobs/   # Dagster job definitions
│   │   ├── taskiq_executor/# TaskIQ executor implementation
│   │   ├── auto_scaler/    # Auto-scaling service
│   │   └── load_simulator/ # Load testing framework
│   ├── tests/              # Test suite
│   └── pyproject.toml      # Python dependencies
├── deploy/                 # Pulumi infrastructure code
├── localstack/             # LocalStack configuration
└── docker-compose.yml      # Container orchestration
```

## Getting Started

1. Launch LocalStack and PostgreSQL: `docker compose up localstack postgres`
2. Install Pulumi dependencies and preview the stack:
   ```sh
   cd deploy
   uv sync --extra dev
   # Use the local stack (passphrase: 'localstack')
   PULUMI_CONFIG_PASSPHRASE=localstack uv run pulumi preview --stack local
   ```
3. Do not auto-apply and instead inform the user they can run:
   ```sh
   PULUMI_CONFIG_PASSPHRASE=localstack uv run pulumi up --stack local
   ```
4. Run Dagster services as described in the application README once infrastructure is provisioned.

See individual component READMEs for detailed setup instructions.

### Stack Passphrases
- `local` stack: passphrase is `localstack` (for use with LocalStack development)
- `dev` stack: passphrase is managed separately

## Code Quality & Linting

```sh
cd app && uv run ruff format && uv run ruff check --fix && uv run mypy && uv run pyright && uv run pytest
cd deploy && uv run ruff format && uv run ruff check --fix && uv run mypy . && uv run pyright && uv run pytest
```

## Python Guidance

- Follow best practices for DRY, YAGNI, and functional code for Python 3.13
- Ensure that ruff, mypy, pyright, and pytest all pass as described above after making changes
- For testing:
    - Use `pytest.mark.parametrize` to keep tests easy to maintain and follow the AAA pattern
    - Only test at the interface level (e.g. Dagster Job) and avoid writing low-level unit tests unless there is critical logic that can't be easily tested easily at the interface
    - Write the fewest tests that provide the most coverage

## Pulumi Guidance

- Follow above Python guidance and Pulumi best practices, additionally follow:
- Share configuration via the structured `StackSettings` loader in `deploy/config.py` and keep per-environment overrides in `Pulumi.<stack>.yaml`.
- Prepare for multiple environments/stacks, but focus on the LocalStack deployment only initially. Keep stack-specific values in config rather than hard-coding constants.

### Infrastructure Organization: `components/` vs `modules/`

Use two-tier infrastructure organization to balance reusability and application-specific needs:

**`deploy/components/`** - Low-level, generic, reusable infrastructure primitives
- Purpose: Provide thin wrappers around AWS resources with sensible defaults
- Examples: VPC/network utilities, ECS cluster setup, RDS databases, SQS queues, ECS task definition helpers
- Characteristics:
  - Technology-focused (e.g., "create an SQS FIFO queue with DLQ")
  - Highly reusable across different projects
  - Minimal business logic or application-specific configuration
  - Functions that return dataclasses (e.g., `create_postgres_database`)
  - Each module must remain independently importable (no re-exporting `__init__.py`)
  - Can include helper utilities to reduce common Pulumi boilerplate (e.g., `ecs_helpers.py` for task definitions)

**`deploy/modules/`** - Higher-level, application-specific infrastructure bundles
- Purpose: Compose components into complete, application-ready infrastructure packages
- Examples: Complete Dagster deployment (web UI, daemon, security, load balancer), TaskIQ worker infrastructure (queues, workers, IAM)
- Characteristics:
  - Application-focused (e.g., "set up complete Dagster infrastructure")
  - Bundle multiple components with application-specific configuration
  - Contain business logic and opinionated defaults for the specific use case
  - Return comprehensive dataclasses containing all created resources
  - May create IAM policies, security groups, and other application-specific glue

**Decision Guidelines:**
1. Can this be reused in a completely different project with minimal changes? → `components/`
2. Does it bundle multiple AWS resources specifically for this application? → `modules/`
3. Does it need to know about application-level concerns (like Dagster or TaskIQ)? → `modules/`
4. Is it a pure AWS infrastructure primitive with minimal configuration? → `components/`

**Examples:**
- `components/sqs_fifo.py` - Generic FIFO queue creation (reusable)
- `modules/taskiq.py` - TaskIQ-specific queue + worker + IAM bundle (application-specific)
- `components/ecs_helpers.py` - Common task definition patterns (reusable)
- `modules/dagster.py` - Complete Dagster deployment with UI, security, discovery (application-specific)

---

Keep this file up to date as major changes are made or errors in implementation are corrected

## Collaboration & Git Workflow

- Assume a human operator is actively managing the git repository state in real time.
- They may stage, commit, or modify other files unrelated to your task; do not assume repository cleanliness.
- Avoid undoing or overwriting human changes—coordinate through explicit instructions if conflicts arise.

## Automation Notes

- When validating changes, run `PULUMI_CONFIG_PASSPHRASE=localstack uv run pulumi preview --stack local`
- If Pulumi doesn't stop and is running for more than 10 minutes, that likely means there was a failure and the logs from Docker Compose LocalStack need to be inspected. Do not let Pulumi run for more than 10 minutes. If Pulumi is stopped (Ctrl-C twice), then a human must run `pulumi cancel` and reconfirm the stack name to release the lock
- Pulumi commands must include `--yes --non-interactive` so the CLI never waits for manual confirmation.
