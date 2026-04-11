"""
SmartPool - Intelligent Memory Pool System

A sophisticated memory pool solution for Python applications, providing efficient
object reuse with advanced features like automatic tuning, background cleanup,
performance monitoring, and configurable memory management strategies.

Usage:
from smartpool import SmartObjectManager, BytesIOFactory, MemoryPreset

# Create a pool with high-throughput preset
factory = BytesIOFactory()
pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

# Use the pool with context manager
with pool.acquire_context(1024) as buffer:
    buffer.write(b"Hello, World!")

# Clean shutdown
pool.shutdown()
"""

# pylint: disable=duplicate-code

# Configuration system
from .config import (
    MemoryConfig,
    MemoryConfigFactory,
    MemoryPreset,
    MemoryPressure,
    MetricsMode,
    MetricsOverloadPolicy,
    ObjectCreationCost,
    PoolConfiguration,
)

# Main Exceptions
from .core.exceptions import (
    FactoryCreationError,
    FactoryValidationError,
    InvalidPoolSizeError,
    InvalidTTLError,
    PoolAlreadyShutdownError,
    PoolConfigurationError,
    PoolExhaustedError,
    SmartPoolError,
)

# Factory Interface
from .core.factory_interface import ObjectFactory, ObjectState

# Performance and monitoring
from .core.metrics import PerformanceMetrics, ThreadSafeStats

# Core pool manager
from .core.smartpool_manager import PoolContext, SmartObjectManager

# Main public API
__all__ = [
    # Core pool management
    "SmartObjectManager",
    "PoolContext",
    # Configuration
    "MemoryConfig",
    "MemoryConfigFactory",
    "MemoryPreset",
    "PoolConfiguration",
    "MetricsMode",
    "MetricsOverloadPolicy",
    "ObjectCreationCost",
    "MemoryPressure",
    # Factory interface
    "ObjectFactory",
    "ObjectState",
    # Monitoring
    "PerformanceMetrics",
    "ThreadSafeStats",
    # Exceptions principales
    "SmartPoolError",
    "PoolExhaustedError",
    "PoolAlreadyShutdownError",
    "FactoryCreationError",
    "FactoryValidationError",
    "InvalidPoolSizeError",
    "InvalidTTLError",
    "PoolConfigurationError",
]


# Package metadata
__version__ = "2.0.0"
__author__ = "SmartPool Development Team"
__description__ = "Intelligent Memory Pool System for Python"
