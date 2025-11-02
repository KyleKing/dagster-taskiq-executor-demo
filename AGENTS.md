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

## TaskIQ Implementation Notes

While the project is named "dagster-taskiq-executor" and uses TaskIQ-related terminology, the actual worker implementation does not use the TaskIQ framework directly. Instead, it implements a custom async worker using aioboto3 for SQS message consumption.

### Why Not Use the TaskIQ Framework?

The TaskIQ framework was evaluated but ultimately not used for the following reasons:

1. **Dagster Integration Complexity**: TaskIQ's task registration and execution model doesn't align well with Dagster's op/step execution lifecycle. Dagster ops require specific context reconstruction, resource management, and execution metadata that TaskIQ's generic task abstraction doesn't support.

2. **Idempotency Requirements**: The implementation requires exactly-once execution semantics with custom idempotency storage in PostgreSQL. TaskIQ's built-in retry mechanisms and state management are designed for simpler task queues and don't provide the granular control needed for Dagster's execution model.

3. **Custom Payload Handling**: Dagster ops need structured payloads (`OpExecutionTask`) with run/step metadata, execution context, and result reporting. TaskIQ's serialization and payload handling is too generic and would require extensive customization.

4. **Result Reporting**: The executor polls for task completion via idempotency storage rather than TaskIQ's result backend. This allows for better integration with Dagster's run monitoring and failure handling.

5. **Async Execution Control**: The worker needs fine-grained control over async execution, graceful shutdown, and health checks that TaskIQ's broker abstractions don't expose.

The custom implementation provides the necessary control and integration points while maintaining compatibility with TaskIQ's naming conventions and overall architecture patterns.

## Development Setup

> [!IMPORTANT]
> Always run commands from a `zsh` shell so that `mise` automatically loads the configured tool versions. Launch `zsh` explicitly if your environment defaults to another shell.

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

### Initial Setup

1. Launch LocalStack:
   ```sh
   docker compose up -d localstack
   ```

2. Deploy the infrastructure with Pulumi:
   ```sh
   cd deploy
   uv run pulumi up --yes --stack local
   ```
   This creates the ECR repository and other AWS resources in LocalStack.

3. Build and push the application Docker image to LocalStack ECR:
   ```sh
   ./scripts/build-and-push.sh
   ```
   This script uses Docker Bake to build the application image and pushes it to LocalStack ECR using `awslocal`.

4. Run Dagster services as described in the application README once infrastructure is provisioned.

### Development Workflow

**Application code changes:**
1. Rebuild and push the image: `./scripts/build-and-push.sh`
2. Update ECS services to use the new image (Pulumi doesn't need to run again unless infrastructure changes)

**Infrastructure changes:**
1. Update Pulumi code
2. Run: `cd deploy && uv run pulumi up --yes --stack local`

See individual component READMEs for detailed setup instructions.

### Stack Passphrases
- `local` stack: passphrase is `localstack` (for use with LocalStack development)
- `dev` stack: passphrase is managed separately

## Code Quality & Linting

```sh
cd app && uv run ruff format && uv run ruff check --fix && uv run mypy . && uv run pyright && uv run pytest
cd deploy && uv run ruff format && uv run ruff check --fix && uv run mypy . && uv run pyright && uv run pytest
```

## Python Guidance

- Follow best practices for DRY, YAGNI, and functional code for Python 3.13
- Ensure that ruff, mypy, pyright, and pytest all pass as described above after making changes
- For testing:
    - Use `pytest.mark.parametrize` to keep tests easy to maintain and follow the AAA pattern
    - Only test at the interface level (e.g. Dagster Job) and avoid writing low-level unit tests unless there is critical logic that can't be easily tested easily at the interface
    - Write the fewest tests that provide the most coverage

## Testing Guidance

- Validate Dagster behavior end-to-end: job wiring, schedules, configuration loading, and repository completeness.
- Avoid probing Dagster internals or private modules; skip trivial per-op tests unless business logic warrants it.
- Keep test configuration centralized (e.g., `.env.test` fixtures) and favor lightweight boundary mocks such as replacing `asyncio.sleep`.
- Stick to modern APIs like `execute_in_process()` and property accessors when asserting run results and definitions.
- Never structure pytest suites with unittest-style classes or `unittest.TestCase`; use plain functions and parametrization instead.

## Pulumi Guidance

- Follow above Python guidance and Pulumi best practices, additionally follow:
- Share configuration via the structured `StackSettings` loader in `deploy/config.py` and keep per-environment overrides in `Pulumi.<stack>.yaml`.
- Prepare for multiple environments/stacks, but focus on the LocalStack deployment only initially. Keep stack-specific values in config rather than hard-coding constants.

### Infrastructure Organization: `components/` vs `modules/`

**`deploy/components/`** - Generic, reusable AWS primitives
- Technology-focused thin wrappers (VPC, ECS, RDS, SQS)
- Functions returning dataclasses, independently importable (no `__init__.py` re-exports)
- Examples: `sqs_fifo.py`, `ecs_helpers.py`, `rds_postgres.py`

**`deploy/modules/`** - Application-specific infrastructure bundles
- Compose multiple components with application logic
- Know about Dagster, TaskIQ, and other app concerns
- Examples: `dagster.py` (complete deployment), `taskiq.py` (queues + workers + IAM)

**Guideline**: Reusable across projects? → `components/`. Application-specific bundle? → `modules/`

---

Keep this file up to date as major changes are made or errors in implementation are corrected

## Project Status

### Stage 01 – TaskIQ Executor Foundation ✅ COMPLETED
- Implemented TaskIQ executor with SQS-based distributed job execution
- Added idempotency storage using PostgreSQL
- Created payload models for task serialization
- Integrated executor into Dagster jobs
- Comprehensive testing with interface-level mocks

### Stage 02 – TaskIQ Worker Runtime ✅ COMPLETED
- Built TaskIQ worker service consuming from SQS queues
- Implemented worker lifecycle management with graceful shutdown
- Added HTTP health check endpoint for ECS monitoring
- Created CLI entrypoint for worker execution
- Updated Pulumi infrastructure for ECS task definitions
- Configured container commands and environment variables
- Integrated health checks and logging

### Next Steps
- Stage 03: Implement auto-scaling based on queue depth
- Stage 04: Add load simulation and performance testing

## Collaboration & Git Workflow

- Assume a human operator is actively managing the git repository state in real time.
- They may stage, commit, or modify other files unrelated to your task; do not assume repository cleanliness.
- Avoid undoing or overwriting human changes—coordinate through explicit instructions if conflicts arise.

## Automation Notes

- **Pulumi runs locally**: No Docker container required for Pulumi - just run `cd deploy && uv run pulumi <command>` directly
- **Docker Bake for builds**: Images are built using Docker Bake (see `docker-bake.hcl`) via `./scripts/build-and-push.sh`
- **Image Build Separation**: Docker images are built and pushed separately from Pulumi using `./scripts/build-and-push.sh` and the `awslocal` CLI. This avoids networking complexity and uses LocalStack's well-tested workflow.
- When validating changes, run `cd deploy && uv run pulumi preview --stack local`
- If Pulumi doesn't stop and is running for more than 10 minutes, that likely means there was a failure and the logs from Docker Compose LocalStack need to be inspected. Do not let Pulumi run for more than 10 minutes. If Pulumi is stopped (Ctrl-C twice), then a human must run `cd deploy && pulumi cancel` and reconfirm the stack name to release the lock
- Pulumi commands must include `--yes` for automated deployments so the CLI never waits for manual confirmation.

## Container Image Management

The project uses Docker Bake to simplify container image builds and separates building from infrastructure provisioning:

- **Build Tool**: Docker Bake (config in `docker-bake.hcl`) provides declarative, reproducible builds
- **Build & Push**: Use `./scripts/build-and-push.sh` to build with Bake and push to LocalStack ECR
- **Pulumi**: Only creates the ECR repository and references the pre-built image
- **Why**: This approach avoids networking complexity with Pulumi's docker-build provider and LocalStack ECR, using the well-documented `awslocal` workflow instead

Prerequisites:
- LocalStack running (`docker compose up -d localstack`)
- `awslocal` installed (`uvx awscli-local` or `mise use pipx:awscli-local`)
- `uv` for Python dependency management
- `pulumi` CLI installed locally (or via `mise`)
