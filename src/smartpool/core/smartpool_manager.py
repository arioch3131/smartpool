"""
Adaptive Object Manager - A highly modular and extensible generic memory pool.

This module provides the SmartObjectManager class, which is designed for efficient
object reuse with advanced features like automatic tuning, background cleanup,
performance monitoring, and configurable memory management strategies.
"""

import atexit
import functools
import logging
import threading
import time
from contextlib import contextmanager
from typing import Any, Deque, Dict, Generic, Iterator, Optional, Tuple, TypeVar, Union, cast

from smartpool.config import (
    MemoryConfig,
    MemoryConfigFactory,
    MemoryPreset,
    PoolConfiguration,
)
from smartpool.core.data_models import PooledObject
from smartpool.core.exceptions import (
    ExceptionMetrics,
    ExceptionPolicy,
    ObjectAcquisitionError,
    ObjectStateCorruptedError,
    PoolAlreadyShutdownError,
    SmartPoolError,
    SmartPoolExceptionFactory,
)
from smartpool.core.factory_interface import ObjectFactory, ObjectState
from smartpool.core.managers import (
    ActiveObjectsManager,
    BackgroundManager,
    MemoryManager,
    MemoryOptimizer,
    PoolOperationsManager,
)
from smartpool.core.metrics import PerformanceMetrics, ThreadSafeStats
from smartpool.core.utils import safe_log

T = TypeVar("T")


class PoolContext(Generic[T]):
    """
    A context manager designed to simplify the acquisition and release of objects
    from the `SmartObjectManager`. It ensures that objects are properly released
    back to the pool even if exceptions occur during their use.

    Type parameter:
        T: The type of object managed by this context.
    """

    def __init__(self, pool: "SmartObjectManager[T]", *args: Any, **kwargs: Any) -> None:
        """
        Initializes the PoolContext.

        Args:
            pool (SmartObjectManager): The memory pool instance from which
                to acquire and release objects.
            *args: Positional arguments to pass to the `pool.acquire` method.
            **kwargs: Keyword arguments to pass to the `pool.acquire` method.
        """
        self.pool = pool
        self.args = args
        self.kwargs = kwargs
        self.obj_id: Optional[int] = None
        self.key: Optional[str] = None
        self.obj: Optional[T] = None

    def __enter__(self) -> T:
        """
        Enters the runtime context related to this object.
        Acquires an object from the pool and makes it available for use.

        Returns:
            T: The acquired object instance.

        Raises:
            ObjectAcquisitionError: If the pool fails to acquire an object.
        """
        self.obj_id, self.key, self.obj = self.pool.acquire(*self.args, **self.kwargs)
        if self.obj is None:
            raise ObjectAcquisitionError("Failed to acquire object from pool")
        return self.obj

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exits the runtime context and releases the acquired object back to the pool.
        This method is called automatically when exiting a `with` statement,
        regardless of whether an exception occurred.

        Args:
            exc_type (Optional[Type[BaseException]]): The type of the exception
                that caused the context to be exited.
            exc_val (Optional[BaseException]): The exception instance.
            exc_tb (Optional[TracebackType]): A traceback object encapsulating
                the call stack at the point where the exception originally occurred.
        """
        if self.obj_id is not None and self.key is not None and self.obj is not None:
            self.pool.release(self.obj_id, self.key, self.obj)


class SmartObjectManager(Generic[T]):  # pylint: disable=too-many-instance-attributes
    """
    A highly modular and extensible generic memory pool designed for efficient
    object reuse. This class focuses on the core logic of object acquisition and
    release, delegating complex responsibilities such as object validation,
    cleanup, statistics, and optimization to specialized manager classes.

    This architecture promotes separation of concerns, testability, and flexibility,
    allowing different strategies for each aspect of pool management to be plugged in.

    Type parameter:
        T: The type of objects that this memory pool will manage.
    """

    def __init__(
        self,
        factory: ObjectFactory[T],
        default_config: Optional[MemoryConfig] = None,
        preset: Optional[MemoryPreset] = None,
        pool_config: Optional[PoolConfiguration] = None,
    ):
        """
        Initializes the SmartObjectManager with a modular architecture.

        Args:
            factory (ObjectFactory[T]): An instance of an `ObjectFactory`
                responsible for creating, resetting, validating, and destroying
                pooled objects.
            default_config (Optional[MemoryConfig]): An optional `MemoryConfig`
                object to use as the base configuration for the pool. If not
                provided, a default `MemoryConfig` will be used.
            preset (Optional[MemoryPreset]): An optional `MemoryPreset` to apply
                a predefined configuration strategy (e.g., HIGH_THROUGHPUT,
                LOW_MEMORY). If a preset is provided, `default_config` will
                override specific parameters.
            pool_config (Optional[PoolConfiguration]): Configuration for pool
                behavior including max objects, monitoring, and atexit registration.
        """
        # Use default pool configuration if none provided
        pool_config = pool_config or PoolConfiguration()

        # Base configuration
        self.factory = factory
        self.max_total_objects = pool_config.max_total_objects
        self.enable_monitoring = pool_config.enable_monitoring
        self.performance_metrics: Union[PerformanceMetrics, None] = None
        self._is_shut_down: bool = False

        # Configuration with preset
        self._initialize_config(default_config, preset)

        # Core data structures (MINIMAL)
        # Stores pooled objects, organized by their unique key. Each key maps to
        # a deque of PooledObject.
        self.pool: Dict[str, Deque[PooledObject]] = {}
        # Internal pooled-object counter to avoid repeated full scans of `self.pool`.
        self._total_pooled_objects = 0
        # Stores key-specific configurations that override the default_config.
        self.key_configs: Dict[str, MemoryConfig] = {}
        # A reentrant lock to ensure thread-safe access to shared pool data structures.
        self.lock = threading.RLock()

        # LRU cache for `factory.get_key` to optimize key resolution, especially
        # for complex key generation.
        self._get_key_cache = functools.lru_cache(maxsize=128)(self.factory.get_key)

        # Basic statistics manager for general pool metrics.
        self.stats = ThreadSafeStats()

        # Logger for pool-related messages.
        self.logger = logging.getLogger(__name__)
        if self.default_config.enable_logging:
            self.logger.setLevel(logging.DEBUG)

        # Exception management
        self.exception_policy = ExceptionPolicy()
        self.exception_metrics = ExceptionMetrics()

        # === DELEGATION TO SPECIALIZED MANAGERS ===
        self._initialize_managers()
        self._initialize_background_services(pool_config.register_atexit)

    def _initialize_config(
        self, default_config: Optional[MemoryConfig], preset: Optional[MemoryPreset]
    ) -> None:
        """
        Initializes the pool's configuration, applying a preset if specified and then
        overriding with any provided default configuration parameters.

        Args:
            default_config (Optional[MemoryConfig]): The user-provided default configuration.
            preset (Optional[MemoryPreset]): The preset to apply.
        """
        self.current_preset = preset or MemoryPreset.CUSTOM

        if preset is not None:
            # Create config from preset first
            self.default_config = MemoryConfigFactory.create_preset(preset)
            if default_config is not None:
                # Override preset values with explicitly provided default_config values
                self._override_config_params(default_config)
        else:
            # If no preset, use provided default_config or a new default MemoryConfig
            self.default_config = default_config or MemoryConfig()

    def _override_config_params(self, override_config: MemoryConfig) -> None:
        """
        Overrides parameters in the `self.default_config` with values from
        `override_config` only if they are different from the default values
        of a fresh `MemoryConfig` instance. This prevents overriding preset values
        with default `MemoryConfig` values if the user didn't explicitly set them.

        Args:
            override_config (MemoryConfig): The configuration object containing
                parameters to override.
        """
        default_values = MemoryConfig().__dict__
        for key, value in override_config.__dict__.items():
            # Only override if the value is explicitly set (i.e., not the default
            # default_config value)
            if value != default_values.get(key):
                setattr(self.default_config, key, value)

    def _initialize_managers(self) -> None:
        """
        Initializes all specialized manager classes that handle various aspects
        of the pool's functionality. This method centralizes the instantiation
        of these components.
        """
        # Active objects manager (WeakRefs, tracking of objects currently in use).
        self.active_manager = ActiveObjectsManager(self)

        # Complex operations manager (LRU eviction, object validation,
        # corruption handling).
        self.operations_manager = PoolOperationsManager(self)

        # High-level manager (handles presets, generates reports, provides a
        # higher-level interface).
        self.manager = MemoryManager(self)

        # Optimizer (handles auto-tuning and optimization recommendations),
        # initialized only if monitoring is enabled.
        self.optimizer = MemoryOptimizer(self) if self.enable_monitoring else None

        # Performance metrics collector, initialized based on the pool's configuration.
        if self.default_config.enable_performance_metrics:
            self.performance_metrics = PerformanceMetrics(
                history_size=self.default_config.max_performance_history_size,
                enable_detailed_tracking=self.default_config.enable_acquisition_tracking,
            )
        else:
            self.performance_metrics = None

    def _initialize_background_services(self, register_atexit: bool) -> None:
        """
        Initializes background services, such as the background cleanup manager,
        and registers an atexit hook for graceful shutdown.

        Args:
            register_atexit (bool): If True, registers a shutdown function with `atexit`.
        """
        # Background task manager for periodic cleanups and other background operations.
        self.background_manager = BackgroundManager(self)

        if self.default_config.enable_background_cleanup:
            self.background_manager.start_background_cleanup()

        # Register for automatic shutdown when the program exits.
        if register_atexit:
            atexit.register(self._safe_shutdown)

    # === CORE POOL METHODS ===

    def set_config_for_key(self, key: str, config: MemoryConfig) -> None:
        """
        Sets a specific configuration for objects associated with a given key.
        This allows for fine-grained control over how different types of objects
        are managed.

        Args:
            key (str): The unique key for which to set the configuration.
            config (MemoryConfig): The `MemoryConfig` object to apply to this key.
        """
        with self.lock:
            self.key_configs[key] = config

    def get_config_for_key(self, key: str) -> MemoryConfig:
        """
        Retrieves the effective configuration for a given key. If a key-specific
        configuration exists, it is returned; otherwise, the pool's default
        configuration is used.

        Args:
            key (str): The unique key for which to retrieve the configuration.

        Returns:
            MemoryConfig: The `MemoryConfig` object applicable to the given key.
        """
        return self.key_configs.get(key, self.default_config)

    @contextmanager
    def acquire_context(self, *args: Any, **kwargs: Any) -> Iterator[T]:
        """
        Provides a context manager for acquiring and automatically releasing objects
        from the pool. This is the recommended way to use pooled objects to ensure
        proper resource management.

        Args:
            *args: Positional arguments to pass to the `acquire` method.
            **kwargs: Keyword arguments to pass to the `acquire` method.

        Yields:
            ContextManager[T]: A context manager that yields the acquired object.
        """
        with PoolContext(self, *args, **kwargs) as obj:
            yield obj

    def acquire(self, *args: Any, **kwargs: Any) -> Tuple[int, str, T]:
        """
        Acquires an object from the pool. If a suitable object is available in the pool,
        it is reused; otherwise, a new object is created using the factory.
        This method orchestrates the acquisition process by delegating to specialized
        managers.

        Args:
            *args: Positional arguments to pass to the `factory.get_key` and
                `factory.create` methods.
            **kwargs: Keyword arguments to pass to the `factory.get_key` and
                `factory.create` methods.

        Returns:
            Tuple[int, str, T]: A tuple containing:
                - obj_id (int): The unique ID of the acquired object (for tracking).
                - key (str): The key associated with the acquired object.
                - obj (T): The acquired object instance.
        """
        if self._is_shut_down:
            shutdown_time = self.stats.get_all_metrics().get("gauges", {}).get("shutdown_timestamp")
            raise PoolAlreadyShutdownError(
                "acquire", shutdown_time=cast(Optional[float], shutdown_time)
            )

        start_time = time.time()
        lock_wait_start = start_time
        if self.performance_metrics:
            self.performance_metrics.mark_acquisition_start()

        try:
            with self.lock:
                current_time = time.time()
                lock_wait_time_ms = (current_time - lock_wait_start) * 1000
                # 1. Resolve key and config for the requested object type.
                key = self._get_key_cache(*args, **kwargs)
                config = self.get_config_for_key(key)

                # 2. Update LRU access order for the key.
                self.operations_manager.update_key_access(key, current_time)

                # 3. Search for a valid object in the pool, with retry logic for validation.
                search_result = self.operations_manager.find_valid_object_with_retry(
                    key, current_time, config, self.pool
                )

                # 4. Handle pool hit or miss based on the search result.
                if search_result.success:
                    obj = search_result.object_found
                    if obj is None:
                        raise ObjectStateCorruptedError(
                            pool_key=key,
                            state_info={
                                "reason": "search_result.object_found was None despite success"
                            },
                        )
                    self._handle_pool_hit(obj, key, config, current_time)
                else:
                    obj = self._handle_pool_miss(key, config, *args, **kwargs)

                # 5. Track the acquired object as active (in use by the application).
                obj_id = 0
                if obj:
                    obj_id = self.active_manager.track_active_object(
                        obj.obj, key, obj.estimated_size, obj.created_at, obj.access_count
                    )
                self.stats.increment("borrows")

                # 6. Perform post-acquisition tasks: record metrics and trigger
                # auto-tuning checks.
                self._post_acquire_tasks(key, start_time, search_result.success, lock_wait_time_ms)
                return obj_id, key, obj.obj
        finally:
            if self.performance_metrics:
                self.performance_metrics.mark_acquisition_end()

    def _handle_pool_hit(
        self,
        obj: PooledObject,
        key: str,
        config: MemoryConfig,
        current_time: Optional[float] = None,
    ) -> None:
        """
        Internal method to handle the logic when an object is successfully
        retrieved from the pool (a "hit"). Updates the object's state, access
        time, and increments relevant statistics.

        Args:
            obj (PooledObject): The `PooledObject` instance that was retrieved
                from the pool.
            key (str): The key associated with the object.
            config (MemoryConfig): The configuration applicable to this object's key.
        """
        obj.state = ObjectState.IN_USE
        obj.last_accessed = current_time if current_time is not None else time.time()
        obj.access_count += 1

        self.stats.increment("hits")
        self.stats.increment("reuses")

        if config.enable_logging:
            safe_log(
                self.logger,
                logging.DEBUG,
                f"Pool hit for key {key}, access_count: {obj.access_count}",
            )

    def _handle_pool_miss(
        self, key: str, config: MemoryConfig, *args: Any, **kwargs: Any
    ) -> PooledObject:
        """
        Internal method to handle the logic when no suitable object is found in
        the pool (a "miss"). A new object is created using the factory, and
        relevant statistics are updated.

        Args:
            key (str): The key associated with the object to be created.
            config (MemoryConfig): The configuration applicable to this object's key.
            *args: Positional arguments to pass to the `factory.create` method.
            **kwargs: Keyword arguments to pass to the `factory.create` method.

        Returns:
            PooledObject: The newly created `PooledObject` instance.

        Raises:
            ObjectCreationFailedError: Re-raises any exception that occurs during object
                creation by the factory.
        """
        try:
            raw_obj = self.factory.create(*args, **kwargs)
            created_at = time.time()
            obj = PooledObject(
                obj=raw_obj,
                created_at=created_at,
                last_accessed=created_at,
                access_count=1,
                state=ObjectState.IN_USE,
                estimated_size=self.factory.estimate_size(raw_obj),
            )

            self.stats.increment("creates")
            self.stats.increment("misses")

            if config.enable_logging:
                safe_log(self.logger, logging.DEBUG, f"Pool miss for key {key}, created new object")

            return obj

        except Exception as exc:
            safe_log(self.logger, logging.ERROR, f"Failed to create object for key {key}: {exc}")
            raise SmartPoolExceptionFactory.create_pool_operation_error(
                error_type="creation_failed",
                pool_key=key,
                cause=exc,
                context_kwargs={"attempts": 1},
            ) from exc

    def _post_acquire_tasks(
        self, key: str, start_time: float, hit: bool, lock_wait_time_ms: float = 0.0
    ) -> None:
        """
        Performs various tasks immediately after an object has been acquired
        (either from pool or newly created). These tasks include recording
        performance metrics, updating general monitoring statistics, and
        checking for auto-tuning opportunities.

        Args:
            key (str): The key of the acquired object.
            start_time (float): The timestamp when the acquisition process started.
            hit (bool): True if the object was a pool hit, False if it was a miss
                (newly created).
        """
        # Performance metrics recording.
        if self.performance_metrics:
            total_time = (time.time() - start_time) * 1000
            self.performance_metrics.record_acquisition(
                key=key,
                acquisition_time_ms=total_time,
                hit=hit,
                lock_wait_time_ms=lock_wait_time_ms,
            )

        # General monitoring updates.
        if self.enable_monitoring:
            self._update_basic_metrics()

        # Periodic auto-tuning check.
        if self.optimizer:
            self.optimizer.check_auto_tuning()

    def release(self, obj_id: int, key: str, obj: T) -> None:
        """
        Releases an object back to the pool. This method handles untracking the object,
        validating and resetting it, and then attempting to add it back to the pool.
        If the pool is full or the object is invalid, it will be destroyed.

        Args:
            obj_id (int): The unique ID of the object being released.
            key (str): The key associated with the object.
            obj (T): The object instance to release.
        """

        self.stats.increment("releases")
        # 1. Untrack the object from the active objects manager.
        self.active_manager.untrack_active_object(obj_id)

        # 2. Validate and reset outside the pool lock to reduce lock contention.
        # The object is no longer tracked as active and is not yet visible in the pool.
        config = self.get_config_for_key(key)
        if not self.operations_manager.validate_and_reset_object(obj, key, config):
            # If validation or reset fails, the object is destroyed by operations_manager.
            return

        with self.lock:
            # 3. Determine if the object can be added back to the pool
            # (considering global capacity).
            if self.operations_manager.should_add_to_pool(self.pool, self.max_total_objects):
                # 4. Add the object to the pool.
                self.operations_manager.add_to_pool(key, obj, config, self.pool)
            else:
                # If the pool is full, destroy the object to release resources.
                safe_log(self.logger, logging.INFO, f"Pool full for key {key}, destroying object.")
                try:
                    self.factory.destroy(obj)
                except (ConnectionError, TimeoutError) as exc:
                    # Network connection cleanup errors
                    safe_log(
                        self.logger,
                        logging.WARNING,
                        f"Failed to destroy object during release (network error): {exc}",
                    )
                except (AttributeError, ValueError, TypeError) as exc:
                    # Object state or type errors during destruction
                    safe_log(
                        self.logger,
                        logging.WARNING,
                        f"Failed to destroy object during release (object error): {exc}",
                    )
                except (MemoryError, BufferError) as exc:
                    # Memory-related errors during destruction
                    safe_log(
                        self.logger,
                        logging.ERROR,
                        f"Failed to destroy object during release (memory error): {exc}",
                    )
                except IOError as exc:
                    # File system and resource cleanup errors
                    safe_log(
                        self.logger,
                        logging.WARNING,
                        f"Failed to destroy object during release (filesystem error): {exc}",
                    )

        if self.enable_monitoring:
            self._update_basic_metrics()

    def get_total_pooled_objects(self) -> int:
        """
        Returns the current number of objects stored in the pool.

        This counter is updated incrementally by pool operations to avoid
        recalculating `sum(len(queue) for queue in self.pool.values())` on hot paths.
        """
        return self._total_pooled_objects

    def _adjust_total_pooled_objects(self, delta: int) -> None:
        """
        Adjusts the internal pooled-object counter by `delta`.

        Args:
            delta (int): Positive when adding pooled objects, negative when removing.
        """
        # Defensive clamp to preserve invariant even under exceptional paths.
        self._total_pooled_objects = max(0, self._total_pooled_objects + delta)

    def _update_basic_metrics(self) -> None:
        """
        Updates basic pool metrics such as the number of pooled and active objects.
        These metrics are recorded in the `ThreadSafeStats` instance.
        """
        total_pooled = self.get_total_pooled_objects()
        active_count = self.active_manager.get_active_count()

        self.stats.set_gauge("total_pooled_objects", total_pooled)
        self.stats.set_gauge("active_objects_count", active_count)
        self.stats.record_metrics()

    # === PUBLIC INTERFACE (Delegation to managers) ===

    def get_basic_stats(self) -> Dict[str, Any]:
        """
        Retrieves basic statistics about the memory pool with clearer naming.

        Returns:
            Dict[str, Any]: A dictionary containing comprehensive pool statistics with
                        improved naming and additional per-key information.
        """
        with self.lock:
            stats = self.stats.get_all_metrics()

            # Calculate objects per key (main enhancement)
            objects_per_key = {}
            total_pooled_objects = 0
            empty_keys_count = 0
            max_objects_in_key = 0
            max_objects_key = None

            for key, queue in self.pool.items():
                queue_length = len(queue)
                objects_per_key[key] = queue_length
                total_pooled_objects += queue_length

                if queue_length == 0:
                    empty_keys_count += 1
                elif queue_length > max_objects_in_key:
                    max_objects_in_key = queue_length
                    max_objects_key = key

            # Active objects count
            active_objects_count = self.active_manager.get_active_count()

            # Calculate averages and insights
            total_keys_count = len(self.pool)
            avg_objects_per_key = (
                total_pooled_objects / total_keys_count if total_keys_count > 0 else 0
            )

            # Enhanced statistics with clearer naming
            stats = {
                "counters": stats["counters"],
                "gauges": stats["gauges"],
                "total_pooled_objects": total_pooled_objects,
                "active_objects_count": active_objects_count,
                "total_memory_bytes": self.manager.total_memory,
                "total_managed_objects": total_pooled_objects + active_objects_count,
                "objects_per_key": objects_per_key,
                "pool_keys_count": total_keys_count,
                "keys_with_objects": total_keys_count - empty_keys_count,
                "empty_keys_count": empty_keys_count,
                "avg_objects_per_key": round(avg_objects_per_key, 2),
                "max_objects_in_key": max_objects_in_key,
                "busiest_key": max_objects_key,
                "corrupted_keys_count": len(self.operations_manager.get_corruption_stats()),
                "corruption_details": self.operations_manager.get_corruption_stats(),
            }

            return stats

    def get_detailed_stats(self) -> Dict[str, Any]:
        """
        Retrieves detailed statistics about the pool, including per-key information.
        This method delegates to the `MemoryManager`.

        Returns:
            Dict[str, Any]: A comprehensive dictionary of detailed pool statistics.
        """
        return self.manager.get_detailed_stats()

    def get_performance_report(self, detailed: bool = True) -> Dict[str, Any]:
        """
        Generates a performance report for the pool, including metrics, trends,
        and recommendations. This method delegates to the `MemoryManager`.

        Args:
            detailed (bool): If True, includes more granular performance details.

        Returns:
            Dict[str, Any]: A dictionary containing the performance report.
        """
        return self.manager.get_performance_report(detailed)

    def get_preset_info(self) -> Dict[str, Any]:
        """
        Retrieves information about available pool configuration presets and their
        descriptions. This method delegates to the `MemoryManager`.

        Returns:
            Dict[str, Any]: A dictionary with preset information.
        """
        return self.manager.get_preset_info()

    def switch_preset(self, new_preset: MemoryPreset) -> Dict[str, Any]:
        """
        Switches the pool's configuration to a predefined preset.
        This method delegates to the `MemoryManager`.

        Args:
            new_preset (MemoryPreset): The `MemoryPreset` to switch to.

        Returns:
            Dict[str, Any]: A report detailing the changes made by switching the preset.
        """
        return self.manager.switch_preset(new_preset)

    def enable_auto_tuning(self, interval_seconds: float = 300.0) -> None:
        """
        Enables automatic tuning of pool parameters based on observed performance
        metrics. This method delegates to the `MemoryOptimizer`.

        Args:
            interval_seconds (float): The interval (in seconds) at which auto-tuning
                should run.
        """
        if self.optimizer:
            self.optimizer.enable_auto_tuning(interval_seconds)
        else:
            safe_log(
                self.logger,
                logging.WARNING,
                "Auto-tuning cannot be enabled: optimizer not initialized. "
                "Ensure enable_monitoring is True.",
            )

    def disable_auto_tuning(self) -> None:
        """
        Disables automatic tuning of pool parameters.
        This method delegates to the `MemoryOptimizer`.
        """
        if self.optimizer:
            self.optimizer.disable_auto_tuning()
        else:
            safe_log(
                self.logger,
                logging.WARNING,
                "Auto-tuning cannot be disabled: optimizer not initialized.",
            )

    def get_health_status(self) -> Dict[str, Any]:
        """
        Retrieves the current health status of the pool, including potential
        issues and recommendations. This method delegates to the `MemoryManager`.

        Returns:
            Dict[str, Any]: A dictionary containing the pool's health status.
        """
        return self.manager.get_health_status()

    # === MAINTENANCE METHODS ===

    def clear(self) -> None:
        """
        Completely clears the pool, destroying all pooled objects and untracking
        all active objects. This effectively resets the pool to an empty state.
        """
        with self.lock:
            # Delegate data cleanup to the operations manager.
            destroyed = self.operations_manager.clear_all_data(self.pool)

            # Clear active objects tracking.
            self.active_manager.clear_all()

            # Clear the key cache.
            self._get_key_cache.cache_clear()

            safe_log(
                self.logger,
                logging.INFO,
                f"Pool cleared completely, {destroyed} objects destroyed",
            )

    def force_cleanup(self) -> int:
        """
        Forces an immediate execution of background cleanup tasks.
        This method delegates to the `BackgroundManager`.

        Returns:
            int: The number of objects cleaned up during the forced cleanup.
        """
        result = self.background_manager.force_cleanup_now()

        return cast(int, result.get("objects_cleaned", 0) if result.get("success") else 0)

    def shutdown(self) -> None:
        """
        Performs a full shutdown of the memory pool, stopping all background services,
        clearing all objects, and releasing resources.
        This method should be called when the application is exiting to ensure
        a clean shutdown.
        """
        # Stop all managers and their associated threads/executors.
        self.background_manager.shutdown(wait=True)

        # Clear all pooled and active objects.
        self.clear()

        safe_log(self.logger, logging.INFO, "Pool shut down completely")
        self.stats.set_gauge("shutdown_timestamp", time.time())
        self._is_shut_down = True

    def _safe_shutdown(self) -> None:
        """
        A wrapper for the `shutdown` method, designed to be registered with `atexit`.
        It catches any exceptions during shutdown to prevent the application from
        crashing during exit.
        """
        try:
            self.shutdown()
        except RuntimeError as exc:
            # Threading and runtime errors during shutdown
            safe_log(self.logger, logging.ERROR, f"Threading error during atexit shutdown: {exc}")
        except TimeoutError as exc:
            # Timeout errors when waiting for threads/resources to close
            safe_log(self.logger, logging.ERROR, f"Timeout error during atexit shutdown: {exc}")
        except (AttributeError, ValueError, TypeError) as exc:
            # Object state errors during shutdown
            safe_log(
                self.logger, logging.ERROR, f"Object state error during atexit shutdown: {exc}"
            )
        except IOError as exc:
            # System resource errors during shutdown
            safe_log(
                self.logger, logging.ERROR, f"System resource error during atexit shutdown: {exc}"
            )
        except MemoryError as exc:
            # Memory errors during shutdown
            safe_log(self.logger, logging.CRITICAL, f"Memory error during atexit shutdown: {exc}")

    def _handle_exception(self, exc: "SmartPoolError") -> None:
        """
        Centralized exception handling. Records and decides whether to re-raise.
        """
        self.exception_metrics.record_exception(exc)
        if self.exception_policy.should_raise(type(exc)):
            raise exc

    # === CONTEXT MANAGER SUPPORT ===

    def __enter__(self) -> "SmartObjectManager":
        """
        Enters the runtime context for the SmartObjectManager, allowing it to
        be used with `with` statements.

        Returns:
            SmartObjectManager: The instance of the memory pool itself.
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exits the runtime context for the SmartObjectManager, ensuring a
        clean shutdown. This method is automatically called when exiting a
        `with` statement.

        Args:
            exc_type (Optional[Type[BaseException]]): The type of the exception
                that caused the context to be exited.
            exc_val (Optional[BaseException]): The exception instance.
            exc_tb (Optional[TracebackType]): A traceback object encapsulating
                the call stack at the point where the exception originally occurred.
        """
        self.shutdown()
