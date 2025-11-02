# Testing Best Practices for Dagster Applications

This document outlines the testing philosophy and best practices for this Dagster application.

## Testing Philosophy

### Focus on High-Level Application Logic

Tests should validate **application behavior** rather than Dagster's internal implementation details. The goal is to ensure that:

1. Jobs are correctly composed and structured
2. Jobs execute successfully end-to-end
3. Schedules are configured properly
4. Configuration loads and validates correctly

### What to Test

✅ **DO test:**
- Job definitions and structure (ops are connected correctly)
- Job execution success (integration tests)
- Schedule configurations (cron schedules, job references)
- Repository structure (jobs and schedules exist)
- Configuration loading and validation
- Business logic in custom operators

❌ **DO NOT test:**
- Dagster internal implementation details
- Individual ops in isolation (unless they contain complex business logic)
- Dagster's execution engine behavior
- Mocked Dagster context internals (like `context.op.name` availability)

### Avoid Importing from Dagster Private Modules

**Never import from modules with leading underscores** (e.g., `dagster._core.*`). These are internal APIs that:
- May change without notice
- Are not part of the public API contract
- Indicate you're testing implementation details rather than behavior

## Test Organization

### Test Files

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── test_config.py           # Configuration loading and validation
├── test_dagster_jobs.py     # Job structure and execution (integration)
├── test_repository.py       # Repository definitions and completeness
└── test_schedules.py        # Schedule configurations
```

### Removed Tests

- **`test_dagster_ops.py`** - Removed because it tested individual ops in isolation, requiring mocking of Dagster internals. For this application, the ops are simple load simulators that just sleep - testing individual sleep durations doesn't validate meaningful business logic.

## Configuration and Fixtures

### Using .env.test for Test Configuration

Instead of complex environment variable mocking, use a `.env.test` file with pydantic-settings:

```python
# conftest.py
@pytest.fixture
def test_settings() -> Settings:
    """Create test settings from .env.test file."""
    return Settings(_env_file=".env.test", _env_file_encoding="utf-8")
```

This approach:
- Centralizes test configuration in one file
- Avoids verbose `patch.dict()` mocking
- Makes test configuration more maintainable
- Mirrors production configuration patterns

### Simple Mocks for Performance

For integration tests that would otherwise be slow, use simple mocks that don't touch Dagster internals:

```python
@pytest.fixture
def mock_asyncio_sleep(monkeypatch):
    """Mock asyncio.sleep to make tests run instantly."""
    async def instant_sleep(_duration):
        pass
    monkeypatch.setattr("asyncio.sleep", instant_sleep)
```

**Good:** Mocking `asyncio.sleep` to speed up tests
**Bad:** Mocking `asyncio.get_event_loop()` or Dagster context internals

## Modern Dagster 1.12+ Patterns

### Job Execution

Use `execute_in_process()` for integration tests:

```python
def test_fast_job_execution(dagster_instance):
    """Test fast job executes successfully."""
    result = fast_job.execute_in_process(instance=dagster_instance)

    assert result.success
    assert result.dagster_run.status.name == "SUCCESS"
```

### Definitions API

Use property access instead of method calls:

```python
# ✅ Correct (Dagster 1.12+)
jobs = defs.jobs
schedules = defs.schedules

# ❌ Outdated
jobs = defs.get_job_defs()
schedules = defs.get_schedule_defs()
```

### Job Properties

Use modern property names:

```python
# ✅ Correct (Dagster 1.12+)
ops = job.top_level_node_defs

# ❌ Outdated
ops = job.op_defs
```

### Async Operations

For async ops, use `asyncio.get_running_loop()` instead of deprecated `asyncio.get_event_loop()`:

```python
# ✅ Correct (async functions)
@op
async def my_async_op(context):
    start_time = asyncio.get_running_loop().time()
    # ... async work ...
    end_time = asyncio.get_running_loop().time()

# ✅ Correct (sync functions)
@op
def my_sync_op(context):
    import time
    timestamp = time.time()
    # ... sync work ...
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_dagster_jobs.py

# Run specific test
uv run pytest tests/test_dagster_jobs.py::TestJobExecution::test_fast_job_execution
```

## Test Coverage Metrics

Current test coverage focuses on:
- ✅ 5 job definitions and their structure
- ✅ 5 production schedules + 2 testing schedules
- ✅ Configuration loading and validation
- ✅ Repository completeness and integrity

## When to Add New Tests

Add tests when:
1. Adding new jobs with complex op graphs
2. Adding new schedules or changing schedule configurations
3. Adding configuration fields that need validation
4. Implementing custom business logic in ops (beyond simple load simulation)

Don't add tests for:
1. Testing that Dagster's execution engine works
2. Testing individual trivial ops in isolation
3. Verifying Dagster's internal state management
