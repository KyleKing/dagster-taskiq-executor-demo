# AGENTS.md

## Setup commands

- Use `mise` for tool orchestration, `uv` for Python packages
- Install dependencies (single project): `cd <dir> && mise run install` or (all): `mise run //...:install`
- Start LocalStack: `mise run localstack:start`
- Deploy infrastructure: `cd deploy && mise run pulumi:up`
- Build and push image: `./scripts/build-and-push.sh`
- Start Dagster: `cd dagster-taskiq-demo` and `uv run python -m dagster dev`
- Run all checks (single project): `cd <dir> && mise run checks` or (all): `mise run //...:checks`
- Run all fixes (single project): `cd <dir> && mise run fixes` or (all): `mise run //...:fixes`
- Run tests (single project): `cd <dir> && mise run test` or (all): `mise run //...:test`
- General Python: `cd <dir>` and `uv run python -m <>` (or `source .venv/bin/activate`)

## Code style

- Python 3.13 with functional patterns (DRY, YAGNI)
- Use SQLAlchemy v2 style: import from `sqlalchemy`, use `text()` for SQL strings and handle Result objects appropriately (`.scalar()`, `.scalars()`, `.mappings()`)

## Testing instructions

- Test at interface level (Dagster Job) rather than unit tests
- Avoid probing Dagster internals or private modules and use modern APIs like `execute_in_process()`
- Never use unittest-style classes; use plain functions and parametrization; follow AAA pattern
- Run `cd <dir> && mise run test` for each subproject when making changes, or `mise run //...:test` to run all tests

## Project structure

- `dagster-taskiq-demo/`: Full example application with Dagster jobs and TaskIQ executor
- `dagster-taskiq/`: direct reimplementation based on dagster-celery
- `taskiq-demo/`: Standalone TaskIQ and FastAPI demo (without Dagster)
- `deploy/`: Pulumi infrastructure (components/ = reusable AWS primitives, modules/ = app-specific bundles)

## Development workflow

- Always use `zsh` shell for `mise` auto-loading
