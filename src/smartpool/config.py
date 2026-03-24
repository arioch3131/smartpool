"""
Memory pool configuration module.

This module provides configuration classes and presets for managing memory pools.
It includes predefined configurations optimized for different use cases such as
high throughput, low memory, image processing, database connections, and more.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict

from smartpool.core.exceptions.configuration_error import (
    InvalidPoolSizeError,
    InvalidTTLError,
    PoolConfigurationError,
)


class ObjectCreationCost(Enum):
    """
    Defines the relative cost of creating new objects in the memory pool.
    This enum provides a qualitative estimate that influences pool sizing
    and optimization strategies.

    Attributes:
        LOW: Creating new objects is inexpensive (e.g., simple data structures,
             primitive wrappers). Pool can afford more frequent creation.
        MEDIUM: Creating new objects has moderate cost (e.g., file handles,
                network connections with lightweight setup). Balanced approach.
        HIGH: Creating new objects is expensive (e.g., database connections,
              complex computations, large memory allocations). Pool should
              maximize reuse and maintain larger sizes.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MemoryPressure(Enum):
    """
    Defines the memory availability and pressure level in the environment.
    This enum influences memory management strategies and pool sizing decisions.

    Attributes:
        LOW: Abundant memory available. Pool can be more generous with
             object retention and larger cache sizes.
        NORMAL: Standard memory conditions. Balanced approach between
                performance and memory usage.
        HIGH: Memory-constrained environment. Pool should prioritize
              memory efficiency over raw performance, with aggressive
              cleanup and smaller cache sizes.
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class MemoryPreset(Enum):
    """
    Defines predefined configuration presets for the memory pool.
    Each preset is optimized for a specific use case, providing a quick way to
    configure the pool for common scenarios.

    Attributes:
        HIGH_THROUGHPUT (str): Optimized for fast object acquisition and high reuse rates,
                                typically at the cost of higher memory usage.
        LOW_MEMORY (str): Optimized for strict memory constraints, prioritizing minimal
                          memory footprint over raw performance.
        IMAGE_PROCESSING (str): Tailored for large image objects, balancing memory
                                consumption with processing efficiency.
        DATABASE_CONNECTIONS (str): Configured for managing database connections or similar
                                    long-lived, resource-intensive objects,
                                    emphasizing stability and reuse.
        BATCH_PROCESSING (str): Suited for batch jobs or long-running tasks where objects
                                might be held for extended periods, with less frequent cleanup.
        DEVELOPMENT (str): A verbose preset for development and debugging, with extensive
                           logging and strict corruption detection.
        CUSTOM (str): Represents a user-defined or manually configured pool, not adhering
                      to any specific predefined preset.
    """

    HIGH_THROUGHPUT = "high_throughput"
    LOW_MEMORY = "low_memory"
    IMAGE_PROCESSING = "image_processing"
    DATABASE_CONNECTIONS = "database_connections"
    BATCH_PROCESSING = "batch_processing"
    DEVELOPMENT = "development"
    CUSTOM = "custom"


@dataclass
class MemoryConfig:  # pylint: disable=too-many-instance-attributes
    """
    Represents the configuration for a memory pool. This dataclass holds various
    parameters that control the behavior, performance, and resource usage of the
    `GenericMemoryPool`.

    Attributes:
        max_objects_per_key (int): The maximum number of objects that can be held in the pool
                                   for a specific key. This limits the memory footprint for each
                                   type of pooled object.
        ttl_seconds (float): Time-to-live in seconds for pooled objects. Objects older
                             than this will be considered expired and removed during cleanup.
        cleanup_interval_seconds (float): The interval (in seconds) at which background cleanup
                                  tasks are executed.
        enable_logging (bool): If True, enables detailed logging for pool operations.
        enable_background_cleanup (bool): If True, a background thread will periodically
                                          clean up the pool.
        max_validation_attempts (int): The maximum number of times an object will be
                                       re-validated if it initially fails validation
                                       before being marked as corrupted.
        max_corrupted_objects (int): The number of corrupted objects for a given key
                                          that triggers an alert or warning, indicating
                                          potential issues with the factory.

        # Performance metrics configuration
        enable_performance_metrics (bool): If True, enables the collection of detailed
                                           performance metrics.
        enable_acquisition_tracking (bool): If True, records individual acquisition times for
                                        more granular analysis.
        enable_lock_contention_tracking (bool): If True, tracks time spent waiting for pool locks
                                      to identify contention issues.
        max_performance_history_size (int): The number of historical performance records to keep.

        # Configuration for different usage patterns (hints for auto-tuning)
        max_expected_concurrency (int): An estimate of the maximum number of concurrent threads
                                    or processes that will acquire objects from the pool.
                                    Used for optimization hints.
        object_creation_cost (ObjectCreationCost): A qualitative estimate of how expensive
                                    it is to create a new object (ObjectCreationCost.LOW,
                                    ObjectCreationCost.MEDIUM, ObjectCreationCost.HIGH).
                                    Influences pool sizing strategies.
        memory_pressure (str): A qualitative estimate of memory availability in the
                               environment (MemoryPressure.LOW, MemoryPressure.NORMAL,
                               MemoryPressure.HIGH). Influences memory management strategies.
    """

    max_objects_per_key: int = 20
    ttl_seconds: float = 300.0
    cleanup_interval_seconds: float = 60.0
    enable_logging: bool = False
    enable_background_cleanup: bool = True
    max_validation_attempts: int = 3
    max_corrupted_objects: int = 5  # Max number of corrupted objects before alert

    # New performance metrics
    enable_performance_metrics: bool = True
    enable_acquisition_tracking: bool = True
    enable_lock_contention_tracking: bool = True
    max_performance_history_size: int = 1000

    # Configuration for different usage patterns
    max_expected_concurrency: int = 10  # Expected number of threads
    object_creation_cost: ObjectCreationCost = ObjectCreationCost.MEDIUM  # low, medium, high
    memory_pressure: MemoryPressure = MemoryPressure.NORMAL  # low, normal, high

    def __post_init__(self) -> None:
        """
        Performs validation on the configuration parameters after initialization.
        Ensures that values are within acceptable ranges and types.

        Raises:
            InvalidPoolSizeError: If max_objects_per_key is not positive.
            InvalidTTLError: If ttl_seconds is not positive.
            PoolConfigurationError: If any other configuration parameter has an invalid value.
        """
        if self.max_objects_per_key <= 0:
            raise InvalidPoolSizeError(provided_size=self.max_objects_per_key)
        if self.ttl_seconds <= 0:
            raise InvalidTTLError(provided_ttl=self.ttl_seconds)
        if self.cleanup_interval_seconds <= 0:
            raise PoolConfigurationError(
                "cleanup_interval_seconds must be positive",
                context={"cleanup_interval_seconds": self.cleanup_interval_seconds},
            )
        if self.max_expected_concurrency <= 0:
            raise PoolConfigurationError(
                "max_expected_concurrency must be positive",
                context={"max_expected_concurrency": self.max_expected_concurrency},
            )
        if not isinstance(self.object_creation_cost, ObjectCreationCost):
            raise PoolConfigurationError(
                "object_creation_cost must be a ObjectCreationCost enum value,"
                f" got {type(self.object_creation_cost)}"
            )
        if not isinstance(self.memory_pressure, MemoryPressure):
            raise PoolConfigurationError(
                "memory_pressure must be a MemoryPressure enum value,"
                f" got {type(self.memory_pressure)}"
            )

    @classmethod
    def from_dict(cls, config_params: Dict[str, object]) -> "MemoryConfig":
        """Create MemoryConfig from dictionary."""
        return cls(**config_params)  # type: ignore[arg-type]


class MemoryConfigFactory:
    """
    A factory class responsible for creating `PoolConfig` instances, particularly
    for predefined presets and for auto-tuning configurations based on observed
    metrics.
    """

    # Configuration presets mapping
    _PRESET_CONFIGS = {
        MemoryPreset.HIGH_THROUGHPUT: {
            "max_objects_per_key": 100,
            "ttl_seconds": 1800.0,
            "cleanup_interval_seconds": 120.0,
            "enable_logging": False,
            "enable_background_cleanup": True,
            "max_validation_attempts": 2,
            "max_corrupted_objects": 20,
            "max_expected_concurrency": 50,
            "object_creation_cost": ObjectCreationCost.MEDIUM,
            "memory_pressure": MemoryPressure.NORMAL,
            "enable_performance_metrics": True,
            "enable_acquisition_tracking": True,
            "enable_lock_contention_tracking": True,
            "max_performance_history_size": 2000,
        },
        MemoryPreset.LOW_MEMORY: {
            "max_objects_per_key": 5,
            "ttl_seconds": 60.0,
            "cleanup_interval_seconds": 15.0,
            "enable_logging": False,
            "enable_background_cleanup": True,
            "max_validation_attempts": 1,
            "max_corrupted_objects": 2,
            "max_expected_concurrency": 5,
            "object_creation_cost": ObjectCreationCost.LOW,
            "memory_pressure": MemoryPressure.HIGH,
            "enable_performance_metrics": False,
            "enable_acquisition_tracking": False,
            "enable_lock_contention_tracking": False,
            "max_performance_history_size": 100,
        },
        MemoryPreset.IMAGE_PROCESSING: {
            "max_objects_per_key": 30,
            "ttl_seconds": 600.0,
            "cleanup_interval_seconds": 90.0,
            "enable_logging": True,
            "enable_background_cleanup": True,
            "max_validation_attempts": 3,
            "max_corrupted_objects": 3,
            "max_expected_concurrency": 15,
            "object_creation_cost": ObjectCreationCost.HIGH,
            "memory_pressure": MemoryPressure.HIGH,
            "enable_performance_metrics": True,
            "enable_acquisition_tracking": True,
            "enable_lock_contention_tracking": True,
            "max_performance_history_size": 500,
        },
        MemoryPreset.DATABASE_CONNECTIONS: {
            "max_objects_per_key": 20,
            "ttl_seconds": 3600.0,
            "cleanup_interval_seconds": 300.0,
            "enable_logging": True,
            "enable_background_cleanup": True,
            "max_validation_attempts": 3,
            "max_corrupted_objects": 3,
            "max_expected_concurrency": 25,
            "object_creation_cost": ObjectCreationCost.HIGH,
            "memory_pressure": MemoryPressure.LOW,
            "enable_performance_metrics": True,
            "enable_acquisition_tracking": True,
            "enable_lock_contention_tracking": True,
            "max_performance_history_size": 1000,
        },
        MemoryPreset.BATCH_PROCESSING: {
            "max_objects_per_key": 50,
            "ttl_seconds": 7200.0,
            "cleanup_interval_seconds": 600.0,
            "enable_logging": True,
            "enable_background_cleanup": False,
            "max_validation_attempts": 1,
            "max_corrupted_objects": 10,
            "max_expected_concurrency": 10,
            "object_creation_cost": ObjectCreationCost.MEDIUM,
            "memory_pressure": MemoryPressure.NORMAL,
            "enable_performance_metrics": True,
            "enable_acquisition_tracking": False,
            "enable_lock_contention_tracking": False,
            "max_performance_history_size": 200,
        },
        MemoryPreset.DEVELOPMENT: {
            "max_objects_per_key": 10,
            "ttl_seconds": 30.0,
            "cleanup_interval_seconds": 10.0,
            "enable_logging": True,
            "enable_background_cleanup": True,
            "max_validation_attempts": 3,
            "max_corrupted_objects": 1,
            "max_expected_concurrency": 3,
            "object_creation_cost": ObjectCreationCost.LOW,
            "memory_pressure": MemoryPressure.LOW,
            "enable_performance_metrics": True,
            "enable_acquisition_tracking": True,
            "enable_lock_contention_tracking": True,
            "max_performance_history_size": 100,
        },
    }

    @staticmethod
    def create_preset(preset: MemoryPreset) -> MemoryConfig:
        """
        Creates a `MemoryConfig` instance tailored for a specific use case defined
        by a `MemoryPreset`. Each preset provides a set of optimized default values
        for memory management parameters.

        Args:
            preset (MemoryPreset): The desired configuration preset.

        Returns:
            MemoryConfig: A `MemoryConfig` instance configured according to the specified preset.
        """
        config_params = MemoryConfigFactory._PRESET_CONFIGS.get(preset)

        if config_params is not None:
            return MemoryConfig.from_dict(config_params)

        # CUSTOM or default case
        return MemoryConfig()

    @staticmethod
    def get_preset_recommendations() -> Dict[MemoryPreset, str]:
        """
        Returns a dictionary of usage recommendations for each predefined
        `MemoryPreset`. This helps users choose the most appropriate preset for
        their application's needs.

        Returns:
            Dict[MemoryPreset, str]: A dictionary where keys are `MemoryPreset` enums and values
                                    are descriptive strings explaining their recommended use cases.
        """
        return {
            MemoryPreset.HIGH_THROUGHPUT: (
                "Applications with high load requiring fast response times. "
                "Optimized to reduce object creations and contentions."
            ),
            MemoryPreset.LOW_MEMORY: "Environments with strict memory constraints. "
            "Minimal pool with aggressive cleanup.",
            MemoryPreset.IMAGE_PROCESSING: "Image processing or large objects. "
            "Balance between performance and memory consumption.",
            MemoryPreset.DATABASE_CONNECTIONS: "DB connection pools or network resources. "
            "Strict validation and maximum reuse.",
            MemoryPreset.BATCH_PROCESSING: "Batch processing or long tasks. "
            "Optimized for stability over long periods.",
            MemoryPreset.DEVELOPMENT: "Development and testing. "
            "Full logging and early problem detection.",
            MemoryPreset.CUSTOM: "Custom configuration for specific needs.",
        }

    @staticmethod
    def auto_tune_config(
        base_config: MemoryConfig, observed_metrics: Dict[str, float]
    ) -> MemoryConfig:
        """
        Args:
            base_config (MemoryConfig): The current or base configuration to start from.
            observed_metrics (Dict[str, float]): A dictionary of observed performance
                                                metrics, typically from
                                                `PerformanceMetrics.create_snapshot()`.

        Returns:
            MemoryConfig: A new `MemoryConfig` instance with adjusted parameters aimed
                          at improving performance.
        """
        tuned_config = MemoryConfig(
            max_objects_per_key=base_config.max_objects_per_key,
            ttl_seconds=base_config.ttl_seconds,
            cleanup_interval_seconds=base_config.cleanup_interval_seconds,
            enable_logging=base_config.enable_logging,
            enable_background_cleanup=base_config.enable_background_cleanup,
            max_validation_attempts=base_config.max_validation_attempts,
            max_corrupted_objects=base_config.max_corrupted_objects,
            max_expected_concurrency=base_config.max_expected_concurrency,
            object_creation_cost=base_config.object_creation_cost,
            memory_pressure=base_config.memory_pressure,
            enable_performance_metrics=base_config.enable_performance_metrics,
            enable_acquisition_tracking=base_config.enable_acquisition_tracking,
            enable_lock_contention_tracking=base_config.enable_lock_contention_tracking,
            max_performance_history_size=base_config.max_performance_history_size,
        )

        # Adjustments based on metrics
        hit_rate = observed_metrics.get("hit_rate", 0.5)
        avg_acquisition_time = observed_metrics.get("avg_acquisition_time_ms", 1.0)
        lock_contention = observed_metrics.get("lock_contention_rate", 0.1)

        # If hit rate is low, increase pool size to improve reuse.
        if hit_rate < 0.3:
            tuned_config.max_objects_per_key = min(
                base_config.max_objects_per_key * 2, 200
            )  # Double size, up to 200
            tuned_config.ttl_seconds = min(
                base_config.ttl_seconds * 1.5, 3600
            )  # Increase TTL by 50%, up to 1 hour

        # If acquisition time is high, reduce validation attempts for faster operations.
        if avg_acquisition_time > 10.0:
            tuned_config.max_validation_attempts = max(1, base_config.max_validation_attempts - 1)
            tuned_config.max_objects_per_key = int(
                min(base_config.max_objects_per_key * 1.5, 150)
            )  # Also increase size to reduce misses

        # If high contention, adjust cleanup interval to reduce lock contention.
        if lock_contention > 0.3:
            tuned_config.cleanup_interval_seconds = (
                base_config.cleanup_interval_seconds * 2
            )  # Reduce cleanup frequency
            tuned_config.max_validation_attempts = max(
                1, base_config.max_validation_attempts - 1
            )  # Reduce validation attempts

        return tuned_config


@dataclass
class PoolConfiguration:
    """Configuration container for SmartObjectManager initialization."""

    max_total_objects: int = 200
    enable_monitoring: bool = True
    register_atexit: bool = True
