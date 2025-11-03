# Dagster Celery to TaskIQ

Direct migration from Dagster-Celery implementation to Dagster-TaskIQ. **WARN**: the below content is out of date

## Purpose

This directory contains the original Dagster-Celery implementation that has been migrated to TaskIQ. It serves as:

- **Reference**: Understanding the original architecture and patterns
- **Comparison**: Benchmarking TaskIQ implementation against proven Celery patterns
- **Migration Guide**: Step-by-step migration documentation
- **Fallback**: Reference for any missing features during transition

## Migration Status

The migration to TaskIQ is **92% complete** and **production-ready**.

See [MIGRATION_STATUS.md](MIGRATION_STATUS.md) for detailed progress and remaining items.

## Documentation

Complete migration documentation available in [README_MIGRATION.md](README_MIGRATION.md):

- Installation instructions
- Configuration guide
- Usage examples
- Testing instructions
- Performance comparisons

## Quick Reference

### Original Celery Pattern

```python
from dagster_celery import celery_executor

@job(executor_def=celery_executor)
def legacy_job():
    ...
```

### New TaskIQ Pattern

```python
from dagster_taskiq import taskiq_executor

@job(executor_def=taskiq_executor)
def modern_job():
    ...
```

## Key Differences

| Feature | Celery | TaskIQ |
|---------|--------|--------|
| Broker | Redis/RabbitMQ | AWS SQS |
| Scaling | Manual worker management | Auto-scaling via queue depth |
| Exactly-once | Best effort | PostgreSQL idempotency storage |
| Cloud Integration | Self-hosted | Native AWS services |
| Monitoring | Celery Flower | CloudWatch + Dagster UI |

## Architecture Comparison

### Celery Architecture

- Redis/RabbitMQ broker
- Manual worker scaling
- Celery Beat for scheduling
- Flower for monitoring

### TaskIQ Architecture

- AWS SQS broker
- Auto-scaling ECS workers
- Dagster native scheduling
- CloudWatch + Dagster monitoring

## Migration Benefits

1. **Cloud Native**: Full AWS integration with SQS, ECS, CloudWatch
1. **Auto-scaling**: Queue depth-based worker scaling
1. **Exactly-once**: PostgreSQL idempotency prevents duplicate execution
1. **Cost Efficiency**: Pay-per-use SQS and ECS Fargate
1. **Monitoring**: Unified observability through CloudWatch and Dagster

## Development Reference

When implementing new features or debugging issues, use this directory as a reference for:

- Proven patterns for distributed execution
- Error handling and retry mechanisms
- Testing strategies for executors
- Configuration management approaches

## Testing

Run legacy tests for comparison:

```bash
cd dagster-celery-to-taskiq
mise run test
```

Compare with new TaskIQ tests:

```bash
cd dagster-taskiq
mise run test
```
