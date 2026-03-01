# Configuration & Performance Tuning Guide

## Overview

The Adaptive Memory Pool system provides extensive configuration options and automatic tuning capabilities to optimize performance for different use cases. This guide covers configuration presets, manual tuning parameters, performance metrics, and optimization strategies.

## Memory Configuration Presets

### Available Presets

The system includes six pre-configured presets optimized for common scenarios
plus one `CUSTOM` mode for manual configurations:

#### HIGH_THROUGHPUT
**Use Case:** Applications with high load requiring fast response times
**Characteristics:**
- Max pool size: 100 objects per key
- TTL: 30 minutes (1800 seconds)
- Expected concurrency: 50 threads
- Performance metrics: Enabled
- Background cleanup: Every 2 minutes

```python
from smartpool.config import MemoryPreset
from smartpool.core.smartpool_manager import SmartObjectManager

pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)
```

#### LOW_MEMORY
**Use Case:** Environments with strict memory constraints
**Characteristics:**
- Max pool size: 5 objects per key
- TTL: 1 minute (60 seconds)  
- Expected concurrency: 5 threads
- Performance metrics: Disabled for lower overhead
- Aggressive cleanup: Every 15 seconds

```python
pool = SmartObjectManager(factory, preset=MemoryPreset.LOW_MEMORY)
```

#### IMAGE_PROCESSING
**Use Case:** Image processing or large object management
**Characteristics:**
- Max pool size: 30 objects per key
- TTL: 10 minutes (600 seconds)
- Object creation cost: High
- Memory pressure: High
- Enhanced validation: 3 attempts

```python
pool = SmartObjectManager(factory, preset=MemoryPreset.IMAGE_PROCESSING)
```

#### DATABASE_CONNECTIONS
**Use Case:** Database connection pools or network resources
**Characteristics:**
- Max pool size: 20 connections per key
- TTL: 1 hour (3600 seconds)
- Strict validation: 3 attempts
- Long-term stability focus
- Comprehensive logging enabled

```python
pool = SmartObjectManager(factory, preset=MemoryPreset.DATABASE_CONNECTIONS)
```

#### BATCH_PROCESSING
**Use Case:** Batch processing or long-running tasks
**Characteristics:**
- Max pool size: 50 objects per key
- TTL: 2 hours (7200 seconds)
- Manual cleanup control
- Optimized for stability over long periods

```python
pool = SmartObjectManager(factory, preset=MemoryPreset.BATCH_PROCESSING)
```

#### DEVELOPMENT
**Use Case:** Development and testing environments
**Characteristics:**
- Max pool size: 10 objects per key
- TTL: 30 seconds
- Full logging and debugging enabled
- Strict corruption detection (threshold: 1)
- Comprehensive performance tracking

```python
pool = SmartObjectManager(factory, preset=MemoryPreset.DEVELOPMENT)
```

## Configuration Parameters

### Core Pool Settings

#### max_objects_per_key
**Purpose:** Maximum number of objects to pool per key
**Impact:** Higher values improve hit rates but consume more memory
**Tuning Guidelines:**
- Start with expected peak concurrent usage
- Monitor hit rates and adjust accordingly
- Consider memory constraints

```python
# Custom configuration
config = MemoryConfig(max_objects_per_key=75)  # 75 objects per key
```

#### ttl_seconds  
**Purpose:** Time-to-live for pooled objects
**Impact:** Longer TTL improves reuse but may retain stale objects
**Tuning Guidelines:**
- Match to object creation cost
- Consider data freshness requirements
- Balance memory usage vs. performance

```python
config = MemoryConfig(ttl_seconds=900.0)  # 15 minutes
```

#### cleanup_interval_seconds
**Purpose:** Frequency of background cleanup operations
**Impact:** More frequent cleanup uses CPU but frees memory faster
**Tuning Guidelines:**
- Shorter intervals for memory-constrained environments
- Longer intervals for stable, long-running applications

```python
config = MemoryConfig(cleanup_interval_seconds=60.0)  # Every minute
```

### Concurrency Settings

#### max_expected_concurrency
**Purpose:** Expected number of concurrent threads accessing the pool
**Impact:** Affects internal sizing and lock contention strategies
**Tuning Guidelines:**
- Set to realistic peak concurrent thread count
- Over-estimation is better than under-estimation
- Monitor lock contention metrics

```python
config = MemoryConfig(max_expected_concurrency=25)
```

#### enable_lock_contention_tracking
**Purpose:** Enable monitoring of threading bottlenecks
**Impact:** Small performance overhead but provides valuable debugging data
**Tuning Guidelines:**
- Enable during performance tuning phases
- Consider disabling in production if overhead is significant

```python
config = MemoryConfig(enable_lock_contention_tracking=True)
```

### Validation and Error Handling

#### max_validation_attempts
**Purpose:** Number of retry attempts for object validation
**Impact:** Higher values improve reliability but increase latency
**Tuning Guidelines:**
- Increase for unreliable objects or network resources
- Decrease for simple, reliable objects
- Monitor validation failure rates

```python
config = MemoryConfig(max_validation_attempts=2)
```

#### max_corrupted_objects
**Purpose:** Maximum corrupted objects before taking action
**Impact:** Lower values provide faster error detection
**Tuning Guidelines:**
- Set to 1 for development/testing
- Use higher values for production stability
- Monitor corruption rates

```python
config = MemoryConfig(max_corrupted_objects=5)
```

### Performance Monitoring

#### enable_performance_metrics
**Purpose:** Enable detailed performance tracking
**Impact:** Provides optimization data with minimal overhead
**Tuning Guidelines:**
- Always enable for production systems
- Essential for auto-tuning functionality

```python
config = MemoryConfig(enable_performance_metrics=True)
```

#### max_performance_history_size
**Purpose:** Number of historical performance samples to retain
**Impact:** Larger history provides better trend analysis
**Tuning Guidelines:**
- 1000-2000 for production systems
- 100-500 for development/testing

```python
config = MemoryConfig(max_performance_history_size=1500)
```

## Auto-Tuning System

### Enabling Auto-Tuning

The system includes automatic configuration optimization based on observed performance metrics:

```python
from smartpool.core.smartpool_manager import SmartObjectManager

# Auto-tuning requires performance metrics to be enabled
config = MemoryConfig(enable_performance_metrics=True)
pool = SmartObjectManager(factory, default_config=config)

# Auto-tuning is performed by the MemoryOptimizer (enabled by default)
if pool.optimizer:
    tuning_applied = pool.optimizer.perform_auto_tuning()
    print(f"Auto-tuning applied: {tuning_applied}")
```

### Auto-Tuning Logic

The system automatically adjusts configuration based on observed metrics:

#### Low Hit Rate (< 50%)
**Action:** Increase pool size
**Reasoning:** More pooled objects improve reuse rates
```python
# Before auto-tuning
hit_rate = 0.35  # 35% hit rate

# System automatically increases max_objects_per_key
# New configuration will have larger pools
```

#### High Acquisition Time (> 15ms average)
**Action:** Reduce validation attempts
**Reasoning:** Fewer validation retries reduce latency
```python
# System detects high latency
avg_acquisition_time = 22.5  # ms

# Reduces max_validation_attempts to speed up acquisitions
```

#### High Lock Contention (> 30%)
**Action:** Increase cleanup interval  
**Reasoning:** Less frequent cleanup reduces lock pressure
```python
# System detects lock contention
lock_contention_rate = 0.45  # 45%

# Increases cleanup_interval_seconds to reduce lock competition
```

### Manual Auto-Tuning

You can trigger auto-tuning manually with custom metrics:

```python
# Get current performance metrics
current_metrics = {
    'hit_rate': 0.65,
    'avg_acquisition_time_ms': 12.0,
    'lock_contention_rate': 0.15
}

# Apply auto-tuning
from smartpool.config import MemoryConfigFactory
base_config = pool.default_config
optimized_config = MemoryConfigFactory.auto_tune_config(base_config, current_metrics)

# Apply the optimized configuration
pool.default_config = optimized_config
```

## Performance Metrics and Monitoring

### Key Performance Indicators

#### Hit Rate
**Definition:** Percentage of requests served from the pool vs. creating new objects
**Target:** > 60% for most applications, > 80% for high-throughput scenarios
**Calculation:** `reuses / (creates + reuses)`

```python
stats = pool.get_basic_stats()
hit_rate = stats['counters']['reuses'] / (stats['counters']['creates'] + stats['counters']['reuses'])
print(f"Current hit rate: {hit_rate:.2%}")
```

#### Average Acquisition Time
**Definition:** Average time to acquire an object from the pool
**Target:** < 20ms for most applications, < 5ms for high-performance scenarios
**Monitoring:** Track trends and spikes

```python
# Get detailed performance report
report = pool.manager.get_performance_report(detailed=True)
avg_time = report['performance']['avg_acquisition_time_ms']
print(f"Average acquisition time: {avg_time:.2f}ms")
```

#### Lock Contention Rate
**Definition:** Percentage of acquisitions that experience lock contention
**Target:** < 20% for healthy systems, < 10% for optimal performance
**Monitoring:** High values indicate threading bottlenecks

```python
contention_rate = report['performance']['lock_contention_rate']
print(f"Lock contention rate: {contention_rate:.2%}")
```

#### Memory Efficiency
**Definition:** Total memory used by pooled objects
**Target:** Stable or slowly growing memory usage
**Monitoring:** Watch for memory leaks or excessive growth

```python
# Get memory usage statistics
stats = pool.get_basic_stats()
total_objects = stats['total_pooled_objects']
print(f"Total pooled objects: {total_objects}")
```

### Comprehensive Performance Reporting

```python
# Generate detailed performance report
report = pool.manager.get_performance_report(detailed=True)

print("=== Performance Report ===")
print(f"Hit Rate: {report['performance']['hit_rate']:.2%}")
print(f"Average Acquisition Time: {report['performance']['avg_acquisition_time_ms']:.2f}ms")
print(f"Lock Contention: {report['performance']['lock_contention_rate']:.2%}")
print(f"Total Requests: {report['performance']['total_requests']}")

# Per-key statistics
for key, stats in report['key_statistics'].items():
    print(f"Key '{key}': {stats['hit_rate']:.2%} hit rate, {stats['avg_time']:.2f}ms avg")
```

## Tuning Strategies by Use Case

### High-Throughput Web Applications

**Objectives:** Maximum performance, acceptable memory usage
**Configuration Strategy:**
```python
config = MemoryConfig(
    max_objects_per_key=100,                    # Large pools for high reuse
    ttl_seconds=1800.0,             # 30-minute TTL
    max_expected_concurrency=50,         # High concurrency support  
    enable_performance_metrics=True, # Monitor performance
    enable_acquisition_tracking=True,    # Track latency
    cleanup_interval_seconds=120.0          # Moderate cleanup frequency
)
```

**Monitoring Focus:**
- Hit rates should exceed 80%
- Acquisition times under 10ms
- Lock contention under 15%

### Memory-Constrained Environments

**Objectives:** Minimal memory footprint, acceptable performance
**Configuration Strategy:**
```python
config = MemoryConfig(
    max_objects_per_key=5,                     # Small pools
    ttl_seconds=60.0,               # Short TTL for quick cleanup
    max_expected_concurrency=10,        # Limited concurrency
    enable_performance_metrics=False, # Reduce overhead
    cleanup_interval_seconds=15.0           # Frequent cleanup
)
```

**Monitoring Focus:**
- Memory usage stability
- Acceptable hit rates (> 40%)
- No memory leaks

### Batch Processing Systems

**Objectives:** Stability over long periods, efficient resource use
**Configuration Strategy:**
```python
config = MemoryConfig(
    max_objects_per_key=30,                    # Moderate pool size
    ttl_seconds=7200.0,             # Long TTL (2 hours)
    enable_background_cleanup=False, # Manual cleanup control
    max_validation_attempts=3,      # Robust validation
    cleanup_interval_seconds=600.0          # Infrequent cleanup
)
```

**Monitoring Focus:**
- Long-term memory stability
- Validation failure rates
- Periodic manual cleanup effectiveness

### Database Connection Pools

**Objectives:** Maximum reuse, connection reliability
**Configuration Strategy:**
```python
config = MemoryConfig(
    max_objects_per_key=25,                    # Pool size matching connection limits
    ttl_seconds=3600.0,             # Long TTL (1 hour)
    max_validation_attempts=3,      # Robust connection validation
    max_corrupted_objects=2,   # Quick detection of bad connections
    enable_logging=True             # Full audit trail
)
```

**Monitoring Focus:**
- Connection validation success rates
- Long-term connection stability
- Pool exhaustion events

## Performance Optimization Techniques

### Pool Size Optimization

**Methodology:**
1. Start with expected peak concurrency as initial pool size
2. Monitor hit rates over representative workload periods
3. Gradually increase pool size until hit rate improvements plateau
4. Balance memory usage against performance gains

```python
# Iterative pool size optimization
pool_sizes = [10, 25, 50, 75, 100]
best_config = None
best_performance = 0

for size in pool_sizes:
    config = MemoryConfig(max_objects_per_key=size)
    # Run representative workload
    # Measure performance
    performance_score = measure_performance(config)
    if performance_score > best_performance:
        best_performance = performance_score
        best_config = config
```

### TTL Optimization

**Methodology:**
1. Analyze object creation cost vs. data freshness requirements
2. Start with conservative TTL values
3. Monitor object age at acquisition time
4. Adjust TTL to balance reuse with freshness

```python
# TTL analysis
report = pool.manager.get_performance_report(detailed=True)
avg_object_age = report['performance']['avg_object_age_ms']

if avg_object_age < ttl_seconds * 0.1 * 1000:  # Objects used within 10% of TTL
    # Can potentially increase TTL for better reuse
    new_ttl = ttl_seconds * 1.5
```

### Concurrency Optimization

**Methodology:**
1. Monitor lock contention rates under load
2. Adjust max_expected_concurrency based on actual thread counts
3. Consider pool partitioning for extreme concurrency scenarios

```python
# Concurrency analysis
contention_rate = report['performance']['lock_contention_rate']

if contention_rate > 0.25:  # High contention
    # Options:
    # 1. Increase max_expected_concurrency
    # 2. Increase cleanup_interval_seconds
    # 3. Consider multiple pool instances
    pass
```

## Troubleshooting Performance Issues

### Low Hit Rates

**Symptoms:** High object creation rates, poor performance
**Diagnosis:**
```python
stats = pool.get_basic_stats()
hit_rate = stats['counters']['reuses'] / (stats['counters']['creates'] + stats['counters']['reuses'])
if hit_rate < 0.5:
    print("WARNING: Low hit rate detected")
```

**Solutions:**
1. Increase pool size (`max_objects_per_key`)
2. Extend TTL (`ttl_seconds`) 
3. Review factory `get_key()` implementation for over-granular keys
4. Check object validation logic for excessive rejections

### High Acquisition Latency

**Symptoms:** Slow response times, high average acquisition times
**Diagnosis:**
```python
report = pool.manager.get_performance_report(detailed=True)
avg_time = report['performance']['avg_acquisition_time_ms']
if avg_time > 20.0:
    print("WARNING: High acquisition latency")
```

**Solutions:**
1. Reduce validation attempts (`max_validation_attempts`)
2. Optimize factory `validate()` method
3. Reduce lock contention through configuration adjustments
4. Profile factory `create()` and `reset()` methods

### Memory Leaks

**Symptoms:** Continuously growing memory usage, pool size increases
**Diagnosis:**
```python
# Monitor pool growth over time
stats_history = []
# Collect stats periodically
for _ in range(10):
    time.sleep(60)
    stats_history.append(pool.get_basic_stats()['total_pooled_objects'])

growth_rate = (stats_history[-1] - stats_history[0]) / len(stats_history)
if growth_rate > 0.1:  # Growing by more than 0.1 objects per minute
    print("WARNING: Possible memory leak detected")
```

**Solutions:**
1. Review factory `reset()` method for incomplete cleanup
2. Check for circular references in managed objects
3. Implement proper `destroy()` method for resource cleanup
4. Reduce TTL to force more frequent object disposal

### Lock Contention

**Symptoms:** High lock contention rates, thread blocking
**Diagnosis:**
```python
contention_rate = report['performance']['lock_contention_rate']
if contention_rate > 0.3:
    print("WARNING: High lock contention")
```

**Solutions:**
1. Increase cleanup intervals to reduce background lock usage
2. Optimize factory methods to reduce time spent in locks
3. Consider multiple pool instances for different object types
4. Review application threading patterns

## Advanced Configuration

### Custom Configuration with Overrides

```python
# Start with a preset and customize specific parameters
base_config = MemoryConfigFactory.create_preset(MemoryPreset.HIGH_THROUGHPUT)

# Create custom configuration with overrides
custom_config = MemoryConfig(
    max_objects_per_key=base_config.max_objects_per_key * 2,        # Double the pool size
    ttl_seconds=base_config.ttl_seconds / 2,  # Half the TTL
    enable_logging=True,                      # Add logging
    # All other parameters inherited from HIGH_THROUGHPUT preset
    cleanup_interval_seconds=base_config.cleanup_interval_seconds,
    max_expected_concurrency=base_config.max_expected_concurrency,
    # ... other parameters as needed
)

pool = SmartObjectManager(factory, default_config=custom_config)
```

### Per-Key Configuration

```python
# Set specific configurations for different object types
pool.set_config_for_key("large_images", MemoryConfig(
    max_objects_per_key=10,        # Fewer large objects
    ttl_seconds=300.0,  # Shorter TTL for large objects
))

pool.set_config_for_key("small_buffers", MemoryConfig(
    max_objects_per_key=100,       # More small objects
    ttl_seconds=1800.0, # Longer TTL for small objects
))
```

### Dynamic Configuration Updates

```python
# Update configuration during runtime
new_config = MemoryConfig(max_objects_per_key=150)
pool.manager.switch_preset(MemoryPreset.HIGH_THROUGHPUT)

# Or update specific parameters
pool.default_config.max_objects_per_key = 150
pool.default_config.ttl_seconds = 2400.0  # 40 minutes
```

This comprehensive guide provides the foundation for optimizing your adaptive memory pool configuration for maximum performance across various use cases and environments.
