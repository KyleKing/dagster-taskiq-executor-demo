# AGENTS.md

## Setup commands

- Install dependencies: `mise run install`
- Start LocalStack: `mise run localstack:start`
- Deploy infrastructure: `cd deploy && mise run pulumi:up`
- Build and push image: `./scripts/build-and-push.sh`
- Start Dagster: `cd dagster-taskiq-demo && python -m dagster dev`
- Run tests: `mise run test`
- Run all checks: `mise run checks`

## Code style

- Python 3.13 with functional patterns (DRY, YAGNI)
- Use SQLAlchemy v2 style: import from `sqlalchemy`, use `text()` for SQL strings
- Handle Result objects appropriately (`.scalar()`, `.scalars()`, `.mappings()`)
- Single quotes, no semicolons where applicable

## Testing instructions

- Test at interface level (Dagster Job) rather than unit tests
- Use `pytest.mark.parametrize` and AAA pattern
- Avoid probing Dagster internals or private modules
- Use modern APIs like `execute_in_process()`
- Never use unittest-style classes; use plain functions and parametrization
- Run `mise run test` for all tests, `mise run lint --fix` for auto-fixing

## Project structure

- `dagster-taskiq-demo/`: Main application with Dagster jobs and TaskIQ executor
- `deploy/`: Pulumi infrastructure (components/ = reusable AWS primitives, modules/ = app-specific bundles)
- `dagster-celery/`: Legacy Dagster-Celery implementation for migration reference
- `taskiq-demo/`: Standalone TaskIQ demo

## Key implementation notes

- Custom async worker implementation (not TaskIQ framework) for better Dagster integration
- Exactly-once execution via PostgreSQL idempotency storage
- Auto-scaling based on SQS queue depth
- Load simulator for testing various scenarios
- Use `mise` for tool orchestration, `uv` for Python packages

## Development workflow

- Always use `zsh` shell for `mise` auto-loading
- App changes: rebuild image with `./scripts/build-and-push.sh`
- Infrastructure changes: update Pulumi code and run `pulumi up`
- Pulumi commands need `--yes` for automation
- If Pulumi hangs >10min: `cd deploy && pulumi cancel`
