# Memory Pool System Usage Guide

## Overview

The memory pool system (`smartpool`) is an advanced solution for optimizing memory management and improving the performance of Python applications. It provides intelligent reuse of objects that are expensive to create, complete with monitoring, auto-optimization, and robust error handling.

## Core Architecture

```
SmartObjectManager (Main Pool)
├── ObjectFactory (Interface for creating/validating/destroying objects)
├── MemoryConfig (Pool configuration)
├── Specialized Managers:
│   ├── PoolOperationsManager (Core operations)
│   ├── ActiveObjectsManager (Tracks active objects)
│   ├── BackgroundManager (Background cleanup)
│   ├── MemoryManager (High-level interface)
│   └── MemoryOptimizer (Auto-optimization)
└── Metrics and Monitoring
```

## Quick Start Guide

### 1. Basic Usage

```python
from smartpool.core.smartpool_manager import SmartObjectManager
from smartpool.factories import BytesIOFactory
from smartpool.config import MemoryPreset

# Create a simple pool
factory = BytesIOFactory()
pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

# Use the pool
with pool.acquire_context(1024) as buffer:
    buffer.write(b"Hello, World!")
    # The buffer is automatically released

# Shutdown cleanly
pool.shutdown()
```

### 2. Advanced Configuration

```python
from smartpool.config import MemoryConfig

# Custom configuration
config = MemoryConfig(
    max_size=50,                    # Max 50 objects per key
    ttl_seconds=1800.0,             # 30-minute lifetime
    enable_performance_metrics=True, # Enable metrics
    max_expected_concurrency=100        # Expected 100 concurrent threads
)

pool = SmartObjectManager(factory, default_config=config)
```

### 3. Monitoring

```python
# Basic statistics
stats = pool.get_basic_stats()
if (stats['hits'] + stats['misses']) > 0:
    print(f"Hit rate: {stats['hits']/(stats['hits']+stats['misses']):.2%}")

# Health status
health = pool.get_health_status()
print(f"Status: {health['status']}")

# Full report
report = pool.get_performance_report(detailed=True)
```

## Examples Index

### Basic Examples

| File | Description | Level | Key Concepts |
|---------|-------------|--------|---------------|
| `example_01_basic_bytesio.py` | Fundamental usage of the pool with `BytesIOFactory`. | Beginner | Pool creation, `acquire`/`release`, context managers, basic stats. |
| `example_02_pil_images.py` | Managing a pool of PIL images for batch processing. | Intermediate | Heavy objects, handling multiple formats, memory monitoring. |
| `example_03_database_pool.py` | Pool of SQLAlchemy database sessions. | Intermediate | DB connections, transaction management, error handling, load testing. |
| `example_04_numpy_arrays.py` | Pool of NumPy arrays for scientific computing. | Intermediate | Scientific computing, ML simulation, large array management, data types. |

### Advanced Examples

| File | Description | Level | Key Concepts |
|---------|-------------|--------|---------------|
| `example_05_advanced_features.py` | Exploring the pool's advanced features. | Advanced | Configuration presets, auto-optimization, real-time monitoring, detailed reports. |
| `example_06_custom_factory.py` | Creating custom factories for complex objects. | Advanced | Inheriting `ObjectFactory`, implementing `create`/`reset`/`validate`, custom keys. |
| `example_07_*.py` | Full web integration with Flask and FastAPI. | Advanced | REST APIs, web app lifecycle management, concurrency, load testing client. |
| `example_08_advanced_patterns.py` | Implementation of advanced design patterns. | Expert | Pool hierarchies, decorators, Builder pattern, Adapters, lazy loading, Observability. |

### Tools and Full Integration

| File | Description | Level | Key Concepts |
|---------|-------------|--------|---------------|
| `example_09_debugging_troubleshooting.py` | Tools and techniques for debugging and diagnostics. | Advanced | Performance diagnostics, memory leak detection, contention analysis. |
| `example_10_complete_integration.py` | A complete image processing application project. | Expert | Real-world architecture, combining all concepts, full REST API, job management. |
| `example_11_metrics_modes.py` | Compare `off/sync/async/sampled` metrics modes on the same workload. | Intermediate | Runtime overhead, p95/p99 comparisons, queue-drop visibility. |

## Choosing the Right Factory

### Available Factories

| Factory | Recommended Use | Managed Objects | Performance |
|---------|------------------|--------------|-------------|
| `BytesIOFactory` | I/O buffers, temporary data | `io.BytesIO` | High |
| `PILImageFactory` | Image processing | `PIL.Image` | Good |
| `NumpyArrayFactory` | Scientific computing, ML | `numpy.ndarray` | High |
| `SQLAlchemySessionFactory` | Database sessions | SQLAlchemy Sessions | Medium |
| `MetadataFactory` | Metadata cache, configurations | Dictionaries | High |

### Selection Criteria

- **Creation Cost**: The more expensive the object is to create, the more beneficial the pool.
- **Object Size**: Large objects benefit greatly from reuse to avoid memory allocations.
- **Usage Pattern**: Frequent reuse of the same types of objects maximizes the hit rate.
- **Concurrency**: A large number of threads accessing the same resources will benefit from the pool's centralized management.

## Configuration Presets

### Available Presets

| Preset | Use Case | Max Size | TTL | Expected Concurrency |
|--------|-------------|----------|-----|----------------------|
| `HIGH_THROUGHPUT` | High-load web applications | 100 | 30min | 50 |
| `LOW_MEMORY` | Memory-constrained environments | 5 | 1min | 5 |
| `IMAGE_PROCESSING` | Image processing | 30 | 10min | 15 |
| `DATABASE_CONNECTIONS` | DB connection pools | 20 | 1h | 25 |
| `DEVELOPMENT` | Development and debugging | 10 | 30s | 3 |

### Selecting a Preset

```python
# For a web API
pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

# For an image processing service
pool = SmartObjectManager(factory, preset=MemoryPreset.IMAGE_PROCESSING)
```

## Usage Patterns

### 1. Context Manager (Recommended)

The safest and most recommended method to ensure objects are always returned to the pool.

```python
# Automatic and safe release
try:
    with pool.acquire_context(*args) as obj:
        # use obj
        pass # obj is automatically released, even if an exception occurs
except Exception as e:
    handle_error(e)
```

### 2. Manual Acquisition (Use with caution)

Only necessary in specific cases where the object's lifecycle does not fit within a `with` block.

```python
# Risk of leaks if release is not guaranteed
obj_id, key, obj = pool.acquire(*args)
try:
    # use obj
finally:
    pool.release(obj_id, key, obj)  # MANDATORY in a finally block
```

### 3. Decorators (For simplicity)

Simplifies injecting pool resources into functions. See `example_08_advanced_patterns.py`.

```python
@with_buffer_pool(pool, 1024)
def process_data(buffer, data):
    buffer.write(data)
    return buffer.getvalue()

result = process_data(b"test data")
```

## Monitoring and Observability

### Essential Metrics

1.  **Hit Rate**: Ideally > 60%. A low rate indicates the pool is not effective.
2.  **Average Acquisition Time**: Ideally < 20ms. A high time may indicate contention or expensive object creation.
3.  **Lock Contention Rate**: Ideally < 20%. A high rate indicates bottlenecks in a concurrent environment.
4.  **Active vs. Pooled Objects Ratio**: A high ratio can signal object leaks (objects not being returned).

### Recommended Alerts

Set up alerts for:
- A hit rate below a certain threshold (e.g., 50%).
- A health status (`health_status`) that is not `healthy`.
- A steady increase in memory used by the pool.

## Performance Optimization

### Auto-Optimization

For hands-free management, enable auto-tuning. The pool will adjust its own parameters based on the observed load.

```python
# Enable auto-tuning (checks every 5 minutes)
pool.enable_auto_tuning(interval_seconds=300)
```

### Manual Optimization

Use the recommendations to guide manual adjustments.

```python
# Get recommendations
recommendations = pool.manager.get_optimization_recommendations()

for rec in recommendations['recommendations']:
    print(f"Action: {rec['reason']} -> Change {rec['parameter']} from {rec['current']} to {rec['recommended']}")
```

## Troubleshooting

### Common Issues

| Symptom | Likely Cause | Solution |
|----------|----------------|----------|
| Low hit rate | Pool is too small or TTL is too short. | Increase `max_size` or `ttl_seconds`. |
| Slow acquisition | Object validation is too expensive. | Reduce `max_validation_attempts` or optimize `factory.validate()`. |
| High contention | Background cleanup is too frequent. | Increase `cleanup_interval`. |
| Increasing memory | Objects are not being returned to the pool. | Ensure `with pool.acquire_context(...)` is used everywhere. |
| Corrupted objects | Incorrect logic in the factory. | Check the `validate()` and `reset()` methods of the factory. |

### Diagnostic Tools

The `example_09_debugging_troubleshooting.py` example provides a `PoolDiagnostic` class to generate comprehensive reports.

```python
from examples.example_09_debugging_troubleshooting import PoolDiagnostic

# Automatic diagnostics
diagnostic = PoolDiagnostic(pool)
report = diagnostic.generate_comprehensive_report()

print(f"Problem Severity: {report.issue_severity}")
for issue in report.issues_found:
    print(f"- {issue}")
```
