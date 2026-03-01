System Architecture
===================

Overview of SmartPool's internal architecture and design patterns.

Core Components
---------------

SmartPool's architecture is modular, built around several key components that work together to provide intelligent and efficient object pooling:

Pool Manager (`smartpool.core.smartpool_manager`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :py:class:`~smartpool.core.smartpool_manager.SmartObjectManager` acts as the central coordinator. It is responsible for:
- Orchestrating the overall object lifecycle (acquire, release, shutdown).
- Delegating tasks to specialized sub-managers (operations, active objects, background, memory).
- Applying pooling strategies and coordinating with factories.
- Integrating performance metrics and optimization.

Factory System (`smartpool.core.factory_interface` and `examples/factories`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :py:class:`~smartpool.core.factory_interface.ObjectFactory` defines the pluggable interface for creating, resetting, validating, and destroying pooled objects. This system enables:
- **Object Creation and Destruction:** Custom logic for instantiating and cleaning up diverse object types.
- **State Reset and Validation:** Ensuring objects are in a clean, usable state before reuse.
- **Memory Size Estimation:** Providing insights into the memory footprint of pooled objects.
- **Pool Key Generation:** Determining how objects are uniquely identified within the pool.
Examples of specialized factories are provided in the `examples/factories` directory.

Memory Management (`smartpool.config`, `smartpool.core.managers.memory_manager`, `smartpool.core.managers.memory_optimizer`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This component handles the intelligent allocation and deallocation of pooled resources, featuring:
- **Centralized Configuration (`smartpool.config`):** Defines `MemoryConfig` for pool parameters and `MemoryConfigFactory` for managing predefined presets (e.g., `HIGH_THROUGHPUT`, `LOW_MEMORY`) and dynamic configuration adjustments.
- **High-Level Management (`smartpool.core.managers.memory_manager`):** Provides a facade for administering pool settings, generating comprehensive reports, and offering optimization recommendations.
- **Adaptive Optimization (`smartpool.core.managers.memory_optimizer`):** Implements auto-tuning logic to dynamically adjust pool parameters based on observed performance metrics and memory pressure.

Monitoring & Metrics (`smartpool.core.metrics.performance_metrics`, `smartpool.core.metrics.thread_safe_stats`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A comprehensive monitoring system provides deep insights into the pool's operational health and performance:
- **Performance Metrics (`smartpool.core.metrics.performance_metrics`):** Collects detailed data on acquisition times, hit rates, lock contention, and throughput.
- **Usage Statistics:** Tracks object creation, reuse, and destruction counts.
- **Memory Consumption Tracking:** Monitors the memory footprint of pooled and active objects.
- **Health Indicators:** Provides high-level status (healthy, warning, critical) based on various operational metrics.
- **Thread-Safe Statistics (`smartpool.core.metrics.thread_safe_stats`):** Ensures accurate data collection in concurrent environments.

Exception Handling (`smartpool.core.exceptions`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SmartPool features a robust and granular exception handling system, defined within the `smartpool.core.exceptions` package. This includes:
- **Structured Exception Hierarchy:** Custom exceptions for specific error categories (e.g., configuration, factory, lifecycle, operation, performance, resource errors).
- **Contextual Error Information:** Exceptions carry detailed context to aid in debugging and problem resolution.
- **Management Utilities (`smartpool.core.exceptions.management_utils`):** Provides tools for exception policy enforcement and metrics collection related to errors.

Design Patterns
---------------

Factory Pattern
~~~~~~~~~~~~~~~

The factory pattern enables:
- Pluggable object creation strategies
- Consistent lifecycle management
- Type-safe object handling
- Easy extensibility

Pool Pattern
~~~~~~~~~~~~

The pool pattern provides:
- Resource reuse optimization
- Controlled object lifecycle
- Memory efficiency
- Performance improvement

Observer Pattern
~~~~~~~~~~~~~~~~

Used for:
- Metrics collection
- Event notification
- Status monitoring
- Debug information

Thread Safety
-------------

SmartPool ensures thread safety through:
- Lock-free algorithms where possible
- Fine-grained locking for critical sections
- Thread-local storage for performance
- Atomic operations for counters

For implementation details, see the :doc:`../api/core` documentation.
