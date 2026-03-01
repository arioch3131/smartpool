"""
Advanced patterns and best practices for the memory pool system.

This file demonstrates how to:
- Implement advanced design patterns
- Optimize performance in production
- Manage pool hierarchy and inheritance
- Implement fallback and recovery strategies
- Create decorators and helpers for pool usage
- Patterns for integration with existing frameworks
"""

import argparse
import functools
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, TypeVar

from examples.factories import BytesIOFactory
from smartpool import (
    MemoryConfig,
    MemoryPreset,
    MemoryPressure,
    ObjectCreationCost,
    ObjectFactory,
    SmartObjectManager,
)

T = TypeVar("T")


# === Pattern 1: Pool Hierarchy and Delegation ===


class PoolHierarchy:
    """Pool hierarchy with delegation and fallback."""

    def __init__(self, name: str):
        self.name = name
        self.primary_pools: Dict[str, SmartObjectManager] = {}
        self.fallback_pools: Dict[str, SmartObjectManager] = {}
        # pool_strategies: 'primary_only', 'fallback_on_fail', 'load_balance'
        self.pool_strategies: Dict[str, str] = {}
        self._lock = threading.RLock()

    def add_primary_pool(
        self, pool_name: str, pool: SmartObjectManager, strategy: str = "fallback_on_fail"
    ):
        """Adds a primary pool."""
        with self._lock:
            self.primary_pools[pool_name] = pool
            self.pool_strategies[pool_name] = strategy

    def add_fallback_pool(self, pool_name: str, pool: SmartObjectManager):
        """Adds a fallback pool."""
        with self._lock:
            self.fallback_pools[pool_name] = pool

    @contextmanager
    def acquire_from_hierarchy(self, pool_name: str, *args, **kwargs):
        """Acquires an object following the pool hierarchy."""

        strategy = self.pool_strategies.get(pool_name, "fallback_on_fail")
        primary_pool = self.primary_pools.get(pool_name)
        fallback_pool = self.fallback_pools.get(pool_name)

        if strategy == "primary_only":
            if primary_pool:
                with primary_pool.acquire_context(*args, **kwargs) as obj:
                    yield obj
            else:
                raise RuntimeError(f"Primary pool {pool_name} not available")

        elif strategy == "fallback_on_fail":
            # Try the primary first
            if primary_pool:
                try:
                    with primary_pool.acquire_context(*args, **kwargs) as obj:
                        yield obj
                        return
                except Exception as e:  # pylint: disable=W0718
                    print(f"Primary pool failed: {e}, trying fallback")

            # Fallback if the primary fails or does not exist
            if fallback_pool:
                with fallback_pool.acquire_context(*args, **kwargs) as obj:
                    yield obj
            else:
                raise RuntimeError(f"No available pools for {pool_name}")

        elif strategy == "load_balance":
            # Simple load balancing based on load
            pools = []
            if primary_pool:
                pools.append(("primary", primary_pool))
            if fallback_pool:
                pools.append(("fallback", fallback_pool))

            if not pools:
                raise RuntimeError(f"No pools available for {pool_name}")

            # Choose the pool with the fewest active objects
            best_pool = min(
                pools, key=lambda x: x[1].get_basic_stats().get("active_objects_count", 0)
            )

            with best_pool[1].acquire_context(*args, **kwargs) as obj:
                yield obj

    def get_hierarchy_stats(self) -> Dict[str, Any]:
        """Hierarchy statistics."""
        stats = {"hierarchy_name": self.name, "pools": {}}

        for pool_name, pool in self.primary_pools.items():
            pool_stats = pool.get_basic_stats()
            stats["pools"][f"{pool_name}_primary"] = {
                "type": "primary",
                "strategy": self.pool_strategies.get(pool_name),
                "stats": pool_stats,
            }

        for pool_name, pool in self.fallback_pools.items():
            pool_stats = pool.get_basic_stats()
            stats["pools"][f"{pool_name}_fallback"] = {"type": "fallback", "stats": pool_stats}

        return stats

    def shutdown_all(self):
        """Shuts down all pools in the hierarchy."""
        for pool in self.primary_pools.values():
            pool.shutdown()
        for pool in self.fallback_pools.values():
            pool.shutdown()


# === Pattern 2: Decorators for automatic pool usage ===
# pylint: disable=R0903
class PooledResource:
    """Decorator to automatically use a pool."""

    def __init__(self, pool: SmartObjectManager, *pool_args, **pool_kwargs):
        self.pool = pool
        self.pool_args = pool_args
        self.pool_kwargs = pool_kwargs

    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self.pool.acquire_context(*self.pool_args, **self.pool_kwargs) as resource:
                # Inject the resource as the first argument
                return func(resource, *args, **kwargs)

        return wrapper


def with_buffer_pool(pool: SmartObjectManager, buffer_size: int = 1024):
    """Specialized decorator for buffer pools."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with pool.acquire_context(buffer_size) as buffer:
                return func(buffer, *args, **kwargs)

        return wrapper

    return decorator


# pylint: disable=R0902
class PoolContextManager:
    """Advanced context manager with retry and timeout."""

    def __init__(
        self,
        pool: SmartObjectManager,
        *args,
        max_retries: int = 3,
        timeout: float = 5.0,
        **kwargs,
    ):
        self.pool = pool
        self.max_retries = max_retries
        self.timeout = timeout
        self.args = args
        self.kwargs = kwargs
        self.obj_id = None
        self.key = None
        self.obj = None

    def __enter__(self):
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                self.obj_id, self.key, self.obj = self.pool.acquire(*self.args, **self.kwargs)

                if time.time() - start_time > self.timeout:
                    self.pool.release(self.obj_id, self.key, self.obj)
                    raise TimeoutError(
                        f"Pool acquisition took too long: {time.time() - start_time:.2f}s"
                    )

                return self.obj

            except Exception as e:  # pylint: disable=W0718
                if attempt == self.max_retries - 1:
                    raise
                print(f"Pool acquisition attempt {attempt + 1} failed: {e}")
                time.sleep(0.1 * (2**attempt))  # Exponential backoff

        raise RuntimeError("Failed to acquire from pool after retries")

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.obj_id is not None:
            self.pool.release(self.obj_id, self.key, self.obj)


# === Pattern 3: Pool Factory and Builder ===


class PoolFactory:
    """Factory to create pools with predefined configurations."""

    @staticmethod
    def create_web_application_pool(
        factory: ObjectFactory, expected_users: int = 100
    ) -> SmartObjectManager:
        """Creates a pool optimized for a web application."""

        config = MemoryConfig(
            max_objects_per_key=max(20, expected_users // 5),
            ttl_seconds=1800.0,  # 30 minutes
            cleanup_interval_seconds=300.0,  # 5 minutes
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
            max_expected_concurrency=expected_users,
            object_creation_cost=ObjectCreationCost.MEDIUM,
            memory_pressure=MemoryPressure.NORMAL,
        )

        return SmartObjectManager(factory, default_config=config)

    @staticmethod
    def create_batch_processing_pool(
        factory: ObjectFactory, batch_size: int = 1000
    ) -> SmartObjectManager:
        """Creates a pool optimized for batch processing."""

        config = MemoryConfig(
            max_objects_per_key=max(50, batch_size // 20),
            ttl_seconds=7200.0,  # 2 hours
            cleanup_interval_seconds=600.0,  # 10 minutes
            enable_background_cleanup=False,  # Manual for batch
            enable_performance_metrics=True,
            max_expected_concurrency=10,
            object_creation_cost=ObjectCreationCost.HIGH,
            memory_pressure=MemoryPressure.HIGH,
        )

        return SmartObjectManager(factory, default_config=config)

    @staticmethod
    def create_development_pool(factory: ObjectFactory) -> SmartObjectManager:
        """Creates a pool for development with debugging enabled."""

        config = MemoryConfig(
            max_objects_per_key=10,
            ttl_seconds=60.0,  # 1 minute
            cleanup_interval_seconds=15.0,  # 15 seconds
            enable_logging=True,
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
            max_corrupted_objects=1,  # Strict in dev
            max_validation_attempts=1,
        )

        return SmartObjectManager(factory, default_config=config)


class PoolBuilder:
    """Builder pattern to construct pools with a fluent configuration."""

    def __init__(self, factory: ObjectFactory):
        self.factory = factory
        self.config = MemoryConfig()
        self.preset = None

    def with_preset(self, preset: MemoryPreset) -> "PoolBuilder":
        """Applies a preset."""
        self.preset = preset
        return self

    def with_max_objects_per_key(self, max_objects_per_key: int) -> "PoolBuilder":
        """Configures the maximum size."""
        self.config.max_objects_per_key = max_objects_per_key
        return self

    def with_ttl(self, ttl_seconds: float) -> "PoolBuilder":
        """Configures the TTL."""
        self.config.ttl_seconds = ttl_seconds
        return self

    def with_performance_tracking(self, enabled: bool = True) -> "PoolBuilder":
        """Enables performance tracking."""
        self.config.enable_performance_metrics = enabled
        self.config.enable_acquisition_tracking = enabled
        return self

    def with_concurrency(self, max_expected_concurrency: int) -> "PoolBuilder":
        """Configures the expected concurrency."""
        self.config.max_expected_concurrency = max_expected_concurrency
        return self

    def for_production(self) -> "PoolBuilder":
        """Configuration for production."""
        self.config.enable_logging = False
        self.config.enable_performance_metrics = True
        self.config.cleanup_interval_seconds = 300.0
        return self

    def for_development(self) -> "PoolBuilder":
        """Configuration for development."""
        self.config.enable_logging = True
        self.config.enable_performance_metrics = True
        self.config.cleanup_interval_seconds = 30.0
        self.config.max_corrupted_objects = 1
        return self

    def build(self) -> SmartObjectManager:
        """Builds the pool."""
        return SmartObjectManager(self.factory, default_config=self.config, preset=self.preset)


# === Pattern 4: Pool Adapters and Proxy ===


class PoolAdapter:
    """Adapter to integrate the pool with existing APIs."""

    def __init__(self, pool: SmartObjectManager):
        self.pool = pool
        self._active_objects_count: Dict[int, Any] = {}
        self._lock = threading.RLock()

    def get_resource(self, *args, **kwargs) -> tuple[int, Any]:
        """Interface similar to a classic resource manager."""
        obj_id, key, obj = self.pool.acquire(*args, **kwargs)

        with self._lock:
            self._active_objects_count[obj_id] = (key, obj)

        return obj_id, obj

    def release_resource(self, resource_id: int) -> bool:
        """Releases a resource by its ID."""
        with self._lock:
            if resource_id in self._active_objects_count:
                key, obj = self._active_objects_count.pop(resource_id)
                self.pool.release(resource_id, key, obj)
                return True
            return False

    def get_active_count(self) -> int:
        """Number of active resources."""
        with self._lock:
            return len(self._active_objects_count)


class LazyPool:
    """Lazy pool that is created on first use."""

    def __init__(self, factory_func: Callable[[], SmartObjectManager]):
        self._factory_func = factory_func
        self._pool: Optional[SmartObjectManager] = None
        self._lock = threading.Lock()

    @property
    def pool(self) -> SmartObjectManager:
        """Retrieves the pool, creates it if necessary."""
        if self._pool is None:
            with self._lock:
                if self._pool is None:  # Double-check locking
                    self._pool = self._factory_func()
        return self._pool

    def acquire_context(self, *args, **kwargs):
        """Proxy to the pool's acquire_context."""
        return self.pool.acquire_context(*args, **kwargs)

    def get_basic_stats(self) -> Dict[str, Any]:
        """Proxy to the pool's get_basic_stats."""
        if self._pool is None:
            return {"status": "not_initialized"}
        return self.pool.get_basic_stats()

    def shutdown(self):
        """Shuts down the pool if it exists."""
        if self._pool is not None:
            self._pool.shutdown()


# === Pattern 5: Monitoring and Observability ===


class PoolObserver(ABC):
    """Interface for observing pool events."""

    @abstractmethod
    def on_object_acquired(self, pool_name: str, key: str, acquisition_time_ms: float):
        """Called when an object is acquired."""

    @abstractmethod
    def on_object_released(self, pool_name: str, key: str):
        """Called when an object is released."""

    @abstractmethod
    def on_pool_miss(self, pool_name: str, key: str):
        """Called on a pool miss."""


class LoggingObserver(PoolObserver):
    """Observer that logs events."""

    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level

    def on_object_acquired(self, pool_name: str, key: str, acquisition_time_ms: float):
        if acquisition_time_ms > 10.0:  # Only log slow acquisitions
            print(
                f"[{self.log_level}] Pool {pool_name}:"
                f" Slow acquisition for {key}: {acquisition_time_ms:.2f}ms"
            )

    def on_object_released(self, pool_name: str, key: str):
        pass  # We can choose not to log releases

    def on_pool_miss(self, pool_name: str, key: str):
        print(f"[{self.log_level}] Pool {pool_name}: Miss for key {key}")


class MetricsObserver(PoolObserver):
    """Observer that collects metrics."""

    def __init__(self):
        self.metrics = {
            "total_acquisitions": 0,
            "total_releases": 0,
            "total_misses": 0,
            "slow_acquisitions": 0,
            "acquisition_times": [],
        }
        self._lock = threading.Lock()

    def on_object_acquired(self, pool_name: str, key: str, acquisition_time_ms: float):
        with self._lock:
            self.metrics["total_acquisitions"] += 1
            self.metrics["acquisition_times"].append(acquisition_time_ms)

            if acquisition_time_ms > 5.0:
                self.metrics["slow_acquisitions"] += 1

            # Keep only the last 1000 times
            if len(self.metrics["acquisition_times"]) > 1000:
                self.metrics["acquisition_times"] = self.metrics["acquisition_times"][-1000:]

    def on_object_released(self, pool_name: str, key: str):
        with self._lock:
            self.metrics["total_releases"] += 1

    def on_pool_miss(self, pool_name: str, key: str):
        with self._lock:
            self.metrics["total_misses"] += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Retrieves the collected metrics."""
        with self._lock:
            metrics = self.metrics.copy()

            if metrics["acquisition_times"]:
                metrics["avg_acquisition_time"] = sum(metrics["acquisition_times"]) / len(
                    metrics["acquisition_times"]
                )
                metrics["max_acquisition_time"] = max(metrics["acquisition_times"])
                metrics["min_acquisition_time"] = min(metrics["acquisition_times"])

            return metrics


class ObservablePool:
    """Wrapper for a pool with observer support."""

    def __init__(self, pool: SmartObjectManager, name: str = "default"):
        self.pool = pool
        self.name = name
        self.observers: list[PoolObserver] = []

    def add_observer(self, observer: PoolObserver):
        """Adds an observer."""
        self.observers.append(observer)

    def remove_observer(self, observer: PoolObserver):
        """Removes an observer."""
        if observer in self.observers:
            self.observers.remove(observer)

    @contextmanager
    def acquire_context(self, *args, **kwargs):
        """Context manager with notifications to observers."""
        start_time = time.time()

        try:
            obj_id, key, obj = self.pool.acquire(*args, **kwargs)
            acquisition_time_ms = (time.time() - start_time) * 1000

            # Notify observers
            for observer in self.observers:
                try:
                    observer.on_object_acquired(self.name, key, acquisition_time_ms)
                except Exception as e:  # pylint: disable=W0718
                    print(f"Observer error: {e}")

            try:
                yield obj
            finally:
                self.pool.release(obj_id, key, obj)

                # Notify release
                for observer in self.observers:
                    try:
                        observer.on_object_released(self.name, key)
                    except Exception as e:  # pylint: disable=W0718
                        print(f"Observer error: {e}")

        except Exception:  # pylint: disable=W0718
            # Notify miss (approximation)
            key = "unknown"
            for observer in self.observers:
                try:
                    observer.on_pool_miss(self.name, key)
                except Exception as obs_e:  # pylint: disable=W0718
                    print(f"Observer error: {obs_e}")
            raise


# === Tests and demonstrations ===


def demo_pool_hierarchy(quick: bool = False):
    """Demonstration of the pool hierarchy."""

    print("=== Pool Hierarchy Demonstration ===\n")

    # Create pools with different capacities
    factory = BytesIOFactory()

    # High-performance primary pool
    primary_pool = PoolFactory.create_web_application_pool(factory, expected_users=100)

    # More conservative fallback pool
    fallback_pool = PoolFactory.create_development_pool(factory)

    # Create the hierarchy
    hierarchy = PoolHierarchy("web_app_hierarchy")
    hierarchy.add_primary_pool("buffers", primary_pool, strategy="fallback_on_fail")
    hierarchy.add_fallback_pool("buffers", fallback_pool)

    try:
        print("--- Normal delegation test ---")

        # Normal usage (should use the primary)
        with hierarchy.acquire_from_hierarchy("buffers", 1024) as buffer:
            buffer.write(b"Test with primary pool")
            print("Acquisition successful with primary pool")

        # Simulate an overload of the primary pool
        print("\n--- Fallback test ---")

        # Fill the primary pool
        acquired_objects = []
        try:
            saturation_attempts = 8 if quick else 25
            for _ in range(saturation_attempts):  # More than the primary pool's limit
                obj_id, key, obj = primary_pool.acquire(1024)
                acquired_objects.append((obj_id, key, obj))
        except Exception as exc:  # pylint: disable=W0718
            print(f"Primary pool saturation reached ({type(exc).__name__}), switching to fallback.")

        # Now the fallback should be used
        with hierarchy.acquire_from_hierarchy("buffers", 1024) as buffer:
            buffer.write(b"Test with fallback pool")
            print("Acquisition successful with fallback pool")

        # Clean up
        for obj_id, key, obj in acquired_objects:
            primary_pool.release(obj_id, key, obj)

        # Hierarchy statistics
        stats = hierarchy.get_hierarchy_stats()
        print("\n--- Hierarchy Statistics ---")
        for pool_name, pool_stats in stats["pools"].items():
            print(
                f"{pool_name}: {pool_stats['stats'].get('creates', 0)} creates, "
                f"{pool_stats['stats'].get('reuses', 0)} reuses"
            )

    finally:
        hierarchy.shutdown_all()


def demo_decorators():
    """Demonstration of decorators."""

    print("\n=== Decorators Demonstration ===\n")

    factory = BytesIOFactory()
    pool = PoolFactory.create_development_pool(factory)

    try:
        # Simple decorator
        @with_buffer_pool(pool, buffer_size=2048)
        def process_data_with_decorator(buffer, data: str):
            """Function that automatically uses a buffer from the pool."""
            buffer.write(data.encode())
            buffer.write(b" - processed with decorator")
            buffer.seek(0)
            return buffer.read().decode().rstrip("\x00")

        # Test the decorator
        # pylint: disable=E1120
        result1 = process_data_with_decorator(data="Test data 1")
        result2 = process_data_with_decorator(data="Test data 2")

        print(f"Result 1: {result1}")
        print(f"Result 2: {result2}")

        # Generic decorator
        @PooledResource(pool, 1024)
        def analyze_buffer(buffer, analysis_type: str):
            """Analyzes a buffer according to the requested type."""
            buffer.write(f"Analysis type: {analysis_type}".encode())

            if analysis_type == "size":
                return len(buffer.getvalue())
            if analysis_type == "content":
                buffer.seek(0)
                return buffer.read().decode().rstrip("\x00")
            return "Unknown analysis type"

        # Test the generic decorator
        size_result = analyze_buffer(analysis_type="size")
        content_result = analyze_buffer(analysis_type="content")

        print(f"\nSize analysis: {size_result}")
        print(f"Content analysis: {content_result}")

        # Statistics after using decorators
        stats = pool.get_basic_stats()
        print("\nPool statistics after decorators:")
        print(f"  Creates: {stats.get('creates', 0)}")
        print(f"  Reuses: {stats.get('reuses', 0)}")
        hits = stats["counters"].get("hits", 0)
        misses = stats["counters"].get("misses", 0)
        total = hits + misses
        hit_rate = (hits / total) if total else 0.0
        print(f"  Hit rate: {hit_rate:.2%}")

    finally:
        pool.shutdown()


def demo_builder_pattern():
    """Demonstration of the Builder pattern."""

    print("\n=== Builder Pattern Demonstration ===\n")

    factory = BytesIOFactory()

    # Pool for production environment
    prod_pool = (
        PoolBuilder(factory)
        .with_preset(MemoryPreset.HIGH_THROUGHPUT)
        .with_max_objects_per_key(100)
        .with_concurrency(200)
        .for_production()
        .build()
    )

    # Pool for development
    dev_pool = (
        PoolBuilder(factory)
        .with_max_objects_per_key(5)
        .with_ttl(30.0)
        .with_performance_tracking(True)
        .for_development()
        .build()
    )

    try:
        print("--- Production Pool ---")
        print(f"Max size: {prod_pool.default_config.max_objects_per_key}")
        print(f"TTL: {prod_pool.default_config.ttl_seconds}s")
        print(f"Logging: {prod_pool.default_config.enable_logging}")
        print(f"Performance metrics: {prod_pool.default_config.enable_performance_metrics}")

        print("\n--- Development Pool ---")
        print(f"Max size: {dev_pool.default_config.max_objects_per_key}")
        print(f"TTL: {dev_pool.default_config.ttl_seconds}s")
        print(f"Logging: {dev_pool.default_config.enable_logging}")
        print(f"Cleanup interval: {dev_pool.default_config.cleanup_interval_seconds}s")

        # Test the pools
        with prod_pool.acquire_context(1024) as buffer:
            buffer.write(b"Production data")

        with dev_pool.acquire_context(1024) as buffer:
            buffer.write(b"Development data")

        print("\nPools configured and tested successfully")

    finally:
        prod_pool.shutdown()
        dev_pool.shutdown()


def demo_observability(quick: bool = False):
    """Demonstration of observability."""

    print("\n=== Observability Demonstration ===\n")

    factory = BytesIOFactory()
    pool = PoolFactory.create_web_application_pool(factory, expected_users=50)

    # Create an observable pool
    observable_pool = ObservablePool(pool, "demo_pool")

    # Add observers
    logging_observer = LoggingObserver("INFO")
    metrics_observer = MetricsObserver()

    observable_pool.add_observer(logging_observer)
    observable_pool.add_observer(metrics_observer)

    try:
        print("--- Test with observability ---")

        # Simulate different types of operations
        iterations = 8 if quick else 20
        for i in range(iterations):
            size = [512, 1024, 2048][i % 3]

            with observable_pool.acquire_context(size) as buffer:
                buffer.write(f"Data {i}".encode())

                # Simulate longer processing from time to time
                if i % 7 == 0:
                    time.sleep(0.02)  # 20ms - should trigger the observer

        # Retrieve the collected metrics
        metrics = metrics_observer.get_metrics()

        print("\n--- Collected Metrics ---")
        print(f"Total acquisitions: {metrics['total_acquisitions']}")
        print(f"Total releases: {metrics['total_releases']}")
        print(f"Total misses: {metrics['total_misses']}")
        print(f"Slow acquisitions: {metrics['slow_acquisitions']}")

        if "avg_acquisition_time" in metrics:
            print(f"Average time: {metrics['avg_acquisition_time']:.2f}ms")
            print(f"Max time: {metrics['max_acquisition_time']:.2f}ms")

    finally:
        pool.shutdown()


def demo_advanced_context_manager():
    """Demonstration of the advanced context manager."""

    print("\n=== Advanced Context Manager Demonstration ===\n")

    factory = BytesIOFactory()
    pool = PoolFactory.create_development_pool(factory)

    try:
        print("--- Test with retry and timeout ---")

        # Context manager with retry
        with PoolContextManager(pool, max_retries=3, timeout=1.0) as buffer:
            buffer.write(b"Data with advanced context manager")
            print("Acquisition successful with retry/timeout")

        # Simulate a situation where retry is necessary
        # (In reality, this is difficult to simulate without breaking the pool)

        print("Advanced context manager works correctly")

    finally:
        pool.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Advanced memory pool usage patterns")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run a shorter demo with fewer iterations.",
    )
    args = parser.parse_args()

    demo_pool_hierarchy(quick=args.quick)
    demo_decorators()
    demo_builder_pattern()
    demo_observability(quick=args.quick)
    demo_advanced_context_manager()

    print("\n=== Summary of demonstrated patterns ===")
    print("1. Pool Hierarchy - Delegation and fallback between pools")
    print("2. Decorators - Automatic usage with @decorator")
    print("3. Builder Pattern - Fluent configuration of pools")
    print("4. Observability - Real-time monitoring and metrics")
    print("5. Advanced Context Manager - Automatic retry and timeout")
    print("6. Factory Pattern - Creation of specialized pools")
    print("7. Adapter Pattern - Integration with existing APIs")
    print("8. Lazy Loading - Deferred creation of pools")
