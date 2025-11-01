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

2. Set up LocalStack with Docker Compose (TBD)
3. Deploy infrastructure with Pulumi (TBD, maybe: `cd deploy && uv sync && uv run pulumi preview`)
4. Run Dagster jobs and monitor execution (TBD, maybe: `cd app && uv sync && uv run ..?`)

See individual component READMEs for detailed setup instructions.

## Code Quality & Linting

- **ruff**: Fast Python linter and formatter (with preview mode enabled)
- **mypy**: Static type checker
- **pyright**: Additional static type checker for comprehensive coverage

```bash
cd app && uv run ruff format && uv run ruff check --fix && uv run mypy && uv run pyright
cd deploy && uv run ruff format && uv run ruff check --fix && uv run mypy && uv run pyright
```
