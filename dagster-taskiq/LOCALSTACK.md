# LocalStack Testing Guide

This guide covers known limitations and workarounds when using LocalStack for testing dagster-taskiq.

## Overview

LocalStack provides local AWS service emulation, which is useful for development and testing. However, some SQS features may not work identically to production AWS, which can cause test flakiness.

## Known Limitations


### SQS FIFO Queue Behavior

**Issue**: LocalStack's FIFO queue implementation may have subtle differences from AWS.

**Impact**:
- Message ordering may not be strictly enforced
- Deduplication may behave differently
- Content-based deduplication may not work as expected

**Workaround**:
- Use message group IDs explicitly
- Test FIFO behavior against real AWS for critical paths
- Use standard queues for LocalStack testing when possible

### S3 Extended Payloads

**Status**: ✅ Generally works correctly

**Note**: Large messages (>256KB) are automatically stored in S3. This functionality works well with LocalStack, but ensure:
- S3 bucket is created before use
- Bucket permissions are configured correctly
- Endpoint URLs point to LocalStack

### Message Visibility Timeout

**Issue**: LocalStack may handle visibility timeouts differently than AWS.

**Impact**:
- Messages may become visible earlier or later than expected
- Long-running tasks may cause message redelivery issues

**Workaround**:
- Use shorter visibility timeouts in tests
- Monitor message redelivery in test assertions
- Use generous timeouts for test assertions

## Test Flakiness

### Common Causes

1. **Timing Issues**: LocalStack may process messages faster or slower than AWS
2. **Queue State**: Queue state may not be immediately consistent
3. **Resource Cleanup**: Queues/buckets may not be cleaned up between tests

### Mitigation Strategies

#### 1. Use Generous Timeouts

```python
import time

# Instead of:
time.sleep(0.1)  # May be too short

# Use:
time.sleep(1.0)  # More reliable for LocalStack
```

#### 2. Poll with Backoff

```python
def poll_until_ready(max_wait=10, interval=0.5):
    elapsed = 0
    while elapsed < max_wait:
        if check_condition():
            return True
        time.sleep(interval)
        elapsed += interval
    return False
```

#### 3. Independent Test Fixtures

```python
# Use unique queue names per test
@pytest.fixture
def unique_queue(localstack):
    queue_name = f"test-queue-{int(time.time())}"
    # Create queue with unique name
    yield queue_name
    # Cleanup
```

#### 4. Retry Flaky Tests

```python
@pytest.mark.flaky(max_runs=3, min_passes=1)
def test_flaky_operation():
    # Test that may occasionally fail with LocalStack
    pass
```

#### 5. Mock Critical Paths

For tests that must be deterministic, mock the SQS/S3 interactions:

```python
from unittest.mock import patch, AsyncMock

@patch('boto3.client')
def test_deterministic_behavior(mock_client):
    # Mock SQS responses for deterministic testing
    mock_sqs = AsyncMock()
    mock_client.return_value = mock_sqs
    # Test with mocked responses
```

## Best Practices

### 1. Separate Integration and Unit Tests

- **Unit Tests**: Mock all AWS services, no LocalStack needed
- **Integration Tests**: Use LocalStack, but be tolerant of timing issues

### 2. Use Test-Specific Configuration

```python
# conftest.py
@pytest.fixture
def test_config(localstack):
    return {
        "queue_url": localstack,  # From fixture
        "endpoint_url": "http://localhost:4566",
        "config_source": {
            "wait_time_seconds": 1,  # Shorter for faster tests
            "max_number_of_messages": 1,
        }
    }
```

### 3. Clean Up Resources

```python
@pytest.fixture(autouse=True)
def cleanup_queues(localstack):
    yield
    # Cleanup queues after each test
    sqs = boto3.client('sqs', endpoint_url=localstack)
    # Delete test queues
```

### 4. Document Known Issues

If a test is known to be flaky with LocalStack, document it:

```python
@pytest.mark.localstack_known_issue(
    reason="LocalStack SQS feature not reliable"
)
def test_sqs_feature():
    # Test that may fail with LocalStack
    pass
```

## Troubleshooting

### Tests Pass Locally but Fail in CI

**Possible Causes**:
- Different LocalStack versions
- Network latency differences
- Resource contention

**Solutions**:
- Pin LocalStack version in CI
- Increase test timeouts
- Use test isolation (separate queues per test)

### Messages Not Appearing in Queue

**Check**:
1. Queue URL is correct
2. Endpoint URL points to LocalStack
3. Queue exists (create if needed)
4. Permissions allow send/receive

**Debug**:
```python
import boto3
sqs = boto3.client('sqs', endpoint_url='http://localhost:4566')
response = sqs.get_queue_attributes(
    QueueUrl=queue_url,
    AttributeNames=['All']
)
print(response)
```

### S3 Operations Failing

**Check**:
1. Bucket exists
2. Endpoint URL is correct
3. Credentials are set (even if dummy values)

**Debug**:
```python
import boto3
s3 = boto3.client('s3', endpoint_url='http://localhost:4566')
buckets = s3.list_buckets()
print(buckets)
```

## Alternative Approaches

### 1. Use Real AWS for Critical Tests

For tests that must match production behavior exactly:
- Use a dedicated test AWS account
- Use separate queues/buckets for testing
- Clean up resources after tests

### 2. Use Moto Instead of LocalStack

Moto provides AWS mocking at a different level:
- Better for unit tests
- Less overhead than LocalStack
- May have different limitations

### 3. Hybrid Approach

- Unit tests: Use mocks
- Integration tests: Use LocalStack with tolerance for flakiness
- E2E tests: Use real AWS

## CI/CD Considerations

### LocalStack in CI

```yaml
# Example GitHub Actions
services:
  localstack:
    image: localstack/localstack:latest
    env:
      SERVICES: sqs,s3
      DEBUG: 1
    ports:
      - "4566:4566"
```

### Handling Flaky Tests

1. **Retry Strategy**: Automatically retry failed tests
2. **Mark as Flaky**: Don't fail CI on known flaky tests
3. **Separate Test Suites**: Run flaky tests separately

## See Also

- [LocalStack Documentation](https://docs.localstack.cloud/)
- `TESTING.md` - General testing procedures
- `IMPLEMENTATION_PROGRESS.md` - Known limitations

