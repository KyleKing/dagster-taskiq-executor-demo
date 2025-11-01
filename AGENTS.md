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

## Getting Started

1. Install dependencies with `uv sync`
2. Set up LocalStack with Docker Compose
3. Deploy infrastructure with Pulumi
4. Run Dagster jobs and monitor execution

See individual component READMEs for detailed setup instructions.
