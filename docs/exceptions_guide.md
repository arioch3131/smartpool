# SmartPool Exception Handling Guide

## Overview

SmartPool provides a comprehensive hierarchy of custom exceptions designed for granular error handling and improved observability. This system enables precise error classification, rich debugging context, and flexible error handling policies.

## Exception Hierarchy

### Base Exception

#### SmartPoolError
The base exception for all SmartPool errors, providing rich context for debugging and monitoring.

**Features:**
- Rich context information with timestamp
- Error codes for categorization
- Cause chaining for root cause analysis
- Serialization support for logging/monitoring

**Usage:**
```python
from smartpool.core.exceptions import SmartPoolError

try:
    # Pool operations
    pass
except SmartPoolError as e:
    # Access rich error information
    error_dict = e.to_dict()
    print(f"Error: {e.message}")
    print(f"Context: {e.context}")
    print(f"Timestamp: {e.timestamp}")
```

## Exception Categories

### 1. Configuration Exceptions

#### PoolConfigurationError
Base class for configuration-related errors.

#### InvalidPoolSizeError
Raised when pool size parameters are invalid.

```python
from smartpool.config import MemoryConfig
from smartpool.core.exceptions import InvalidPoolSizeError

# Example: Invalid pool size
try:
    config = MemoryConfig(max_objects_per_key=-1)
except InvalidPoolSizeError as e:
    print(f"Pool size error: {e.message}")
    print(f"Provided size: {e.context['provided_size']}")
```

#### InvalidTTLError
Raised when TTL (Time-To-Live) values are invalid.

```python
from smartpool.config import MemoryConfig
from smartpool.core.exceptions import InvalidTTLError

try:
    config = MemoryConfig(ttl_seconds=-1.0)
except InvalidTTLError as e:
    print(f"TTL error: {e.message}")
```

#### InvalidPresetError
Raised when an invalid configuration preset is specified.

#### ConfigurationConflictError
Raised when configuration parameters conflict with each other.

### 2. Factory Exceptions

#### FactoryError
Base class for factory-related errors, with context about factory class and method.

#### FactoryCreationError
Raised when object creation fails in the factory.

```python
from smartpool.core.exceptions import FactoryCreationError

try:
    obj = factory.create(*args, **kwargs)
except FactoryCreationError as e:
    print(f"Creation failed: {e.message}")
    print(f"Factory: {e.context['factory_class']}")
    print(f"Args count: {e.context['args_count']}")
```

#### FactoryValidationError
Raised when object validation fails.

#### FactoryResetError
Raised when object reset operation fails.

#### FactoryDestroyError
Raised when object destruction fails.

#### FactoryKeyGenerationError
Raised when pool key generation fails.

### 3. Pool Operation Exceptions

#### PoolOperationError
Base class for pool operation errors.

#### ObjectAcquisitionError
Base class for object acquisition errors.

#### PoolExhaustedError
Raised when the pool is exhausted and cannot provide objects.

```python
from smartpool.core.exceptions import PoolExhaustedError

try:
    obj_id, key, obj = pool.acquire()
except PoolExhaustedError as e:
    print(f"Pool exhausted: {e.message}")
    print(f"Utilization: {e.context['utilization_percent']}%")
    print(f"Current/Max: {e.context['current_size']}/{e.context['max_objects_per_key']}")
```

#### AcquisitionTimeoutError
Raised when object acquisition times out.

#### ObjectCreationFailedError
Raised when object creation fails during acquisition.

#### ObjectReleaseError
Base class for object release errors.

#### ObjectValidationFailedError
Raised when object validation fails during release.

#### ObjectResetFailedError
Raised when object reset fails during release.

#### ObjectCorruptionError
Raised when object corruption is detected.

### 4. Lifecycle Exceptions

#### PoolLifecycleError
Base class for pool lifecycle errors.

#### PoolAlreadyShutdownError
Raised when attempting to use a shutdown pool.

```python
from smartpool.core.exceptions import PoolAlreadyShutdownError

try:
    pool.acquire()
except PoolAlreadyShutdownError as e:
    print(f"Pool shutdown: {e.message}")
    print(f"Attempted operation: {e.context['attempted_operation']}")
```

#### PoolInitializationError
Raised when pool initialization fails.

#### BackgroundManagerError
Raised when background task operations fail.

#### ManagerSynchronizationError
Raised when synchronization between managers fails.

### 5. Performance Exceptions

#### PoolPerformanceError
Base class for performance-related errors.

#### HighLatencyError
Raised when operation latency exceeds thresholds.

```python
from smartpool.core.exceptions import HighLatencyError

try:
    # Monitor latency
    if latency > threshold:
        raise HighLatencyError(
            operation="acquire",
            actual_latency_ms=latency,
            threshold_ms=threshold
        )
except HighLatencyError as e:
    print(f"High latency detected: {e.context['latency_ratio']}x threshold")
```

#### LowHitRateError
Raised when hit rate falls below acceptable levels.

#### ExcessiveObjectCreationError
Raised when object creation rate is excessive.

### 6. Resource Exceptions

#### PoolResourceError
Base class for resource-related errors.

#### MemoryLimitExceededError
Raised when memory limits are exceeded.

#### DiskSpaceExhaustedError
Raised when disk space is exhausted.

#### ThreadPoolExhaustedError
Raised when thread pool is exhausted.

#### ResourceLeakDetectedError
Raised when resource leaks are detected.

## Exception Management Utilities

### ExceptionPolicy

Controls exception behavior based on environment and configuration.

```python
from smartpool.core.exceptions import ExceptionPolicy

policy = ExceptionPolicy()
policy.strict_mode = True  # Raise all exceptions in dev/test
policy.log_all_exceptions = True
policy.raise_on_corruption = False

# Check if exception should be raised
if policy.should_raise(exception_type):
    raise exception
else:
    logger.warning(f"Recoverable error: {exception}")
```

### ExceptionMetrics

Collects metrics on exceptions for monitoring and analysis.

```python
from smartpool.core.exceptions import ExceptionMetrics, SmartPoolError

metrics = ExceptionMetrics()

# Record exceptions
error = SmartPoolError("Test error", error_code="TEST_001")
metrics.record_exception(error)

# Access metrics
print(f"Error count: {metrics.exception_counters['TEST_001']}")
```

### SmartPoolExceptionFactory

Factory for creating exceptions with standardized context.

```python
from smartpool.core.exceptions import SmartPoolExceptionFactory

# Create factory exception
factory_error = SmartPoolExceptionFactory.create_factory_error(
    error_type="creation",
    factory_class="BytesIOFactory",
    method_name="create",
    args=(1024,),
    kwargs={"mode": "binary"}
)

# Create pool operation exception
pool_error = SmartPoolExceptionFactory.create_pool_operation_error(
    error_type="exhausted",
    pool_key="buffer_pool",
    current_size=50,
    max_objects_per_key=50,
    active_objects_count=45
)
```

## Best Practices

### 1. Exception Handling in Factories

```python
from smartpool.core.exceptions import FactoryCreationError, FactoryResetError

class CustomFactory(ObjectFactory[MyObject]):
    def create(self, *args, **kwargs):
        try:
            return MyObject(*args, **kwargs)
        except Exception as e:
            raise FactoryCreationError(
                factory_class=self.__class__.__name__,
                args=args,
                kwargs_dict=kwargs,
                cause=e
            )
    
    def reset(self, obj):
        try:
            obj.reset()
            return True
        except Exception as e:
            raise FactoryResetError(
                factory_class=self.__class__.__name__,
                object_type=type(obj).__name__,
                cause=e
            )
```

### 2. Graceful Error Handling

```python
from smartpool.core.exceptions import (
    SmartPoolError, 
    PoolExhaustedError, 
    AcquisitionTimeoutError
)

def safe_acquire_object(pool, timeout=5.0):
    try:
        return pool.acquire(timeout=timeout)
    except PoolExhaustedError:
        # Handle pool exhaustion
        logger.warning("Pool exhausted, trying alternative strategy")
        return None
    except AcquisitionTimeoutError:
        # Handle timeout
        logger.warning("Acquisition timeout, retrying with longer timeout")
        return pool.acquire(timeout=timeout * 2)
    except SmartPoolError as e:
        # Log all SmartPool errors with context
        logger.error(f"Pool error: {e.to_dict()}")
        raise
```

### 3. Monitoring Integration

```python
from smartpool.core.exceptions import ExceptionPolicy, ExceptionMetrics

class MonitoringAwarePool:
    def __init__(self):
        self.exception_policy = ExceptionPolicy()
        self.exception_metrics = ExceptionMetrics()
    
    def handle_exception(self, exception):
        # Record for metrics
        self.exception_metrics.record_exception(exception)
        
        # Apply policy
        if self.exception_policy.should_log(exception):
            logger.error(f"Pool exception: {exception.to_dict()}")
        
        if self.exception_policy.should_raise(type(exception)):
            raise exception
```

### 4. Context Enrichment

```python
from smartpool.core.exceptions import SmartPoolError

def enrich_exception_context(exception, additional_context):
    """Add additional context to existing exception."""
    if isinstance(exception, SmartPoolError):
        exception.context.update(additional_context)
    return exception

# Usage
try:
    pool.acquire()
except SmartPoolError as e:
    e = enrich_exception_context(e, {
        "request_id": "req_123",
        "user_id": "user_456",
        "operation_phase": "initialization"
    })
    raise e
```

## Configuration Examples

### Development Environment

```python
from smartpool.core.exceptions import ExceptionPolicy

# Strict mode for development
policy = ExceptionPolicy()
policy.strict_mode = True
policy.log_all_exceptions = True
policy.raise_on_corruption = True
policy.performance_monitoring = True
```

### Production Environment

```python
# Graceful handling for production
policy = ExceptionPolicy()
policy.strict_mode = False
policy.log_all_exceptions = True
policy.raise_on_corruption = False
policy.max_error_details = 500  # Limit context size
```

## Integration with Existing Code

### Backward Compatibility

The new exception system is designed to be backward compatible. Existing code that catches general `Exception` will continue to work:

```python
# Existing code continues to work
try:
    pool.acquire()
except Exception as e:
    logger.error(f"Pool error: {e}")

# New code can be more specific
try:
    pool.acquire()
except PoolExhaustedError as e:
    # Handle pool exhaustion specifically
    pass
except SmartPoolError as e:
    # Handle all SmartPool errors
    logger.error(f"SmartPool error: {e.to_dict()}")
except Exception as e:
    # Handle any other errors
    logger.error(f"Unexpected error: {e}")
```

### Gradual Migration

Migrate to the new exception system gradually:

1. Start by catching `SmartPoolError` for general SmartPool exceptions
2. Add specific handlers for common exceptions like `PoolExhaustedError`
3. Implement exception policies for environment-specific behavior
4. Add metrics collection for monitoring

This exception system provides robust error handling capabilities while maintaining flexibility and ease of use.
