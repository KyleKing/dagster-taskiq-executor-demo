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
3. Apply the stack against LocalStack when ready:
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
cd deploy && uv run ruff format && uv run ruff check --fix && uv run mypy && uv run pyright && uv run pytest
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
  - Implement reusable infrastructure helpers as functions that return dataclasses (e.g. `create_postgres_database`) instead of component subclasses. Functions live under `deploy/components/` and each module must remain independently importable (no re-exporting `__init__.py`).
  - Share configuration via the structured `StackSettings` loader in `deploy/config.py` and keep per-environment overrides in `Pulumi.<stack>.yaml`.
  - Prepare for multiple environments/stacks, but focus on the LocalStack deployment only initially. Keep stack-specific values in config rather than hard-coding constants.
  - When validating changes, run `PULUMI_CONFIG_PASSPHRASE=localstack uv run pulumi preview --stack local` followed by `PULUMI_CONFIG_PASSPHRASE=localstack uv run pulumi up --stack local` against the LocalStack instance.

---

Keep this file up to date as major changes are made or errors in implementation are corrected
