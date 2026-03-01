"""
Example of creating custom factories for the memory pool system.

This file shows how to:
- Create a custom factory by inheriting from ObjectFactory
- Implement all required methods
- Manage validation and reset of custom objects
- Optimize key generation for pooling
- Integrate the factory with the pool system
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict

from smartpool import MemoryConfig, MemoryPreset, ObjectFactory, SmartObjectManager

# pylint: disable=R0801

# === Example 1: Factory for configuration objects ===


@dataclass
class ConfigObject:
    """Reusable configuration object."""

    name: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    version: int = 1
    _is_dirty: bool = field(default=False, init=False)

    def set_setting(self, key: str, value: Any):
        """Sets a configuration."""
        self.settings[key] = value
        self._is_dirty = True

    def get_setting(self, key: str, default=None):
        """Retrieves a configuration."""
        return self.settings.get(key, default)

    def is_valid(self) -> bool:
        """Checks if the object is valid."""
        return isinstance(self.settings, dict) and isinstance(self.name, str)

    def reset(self):
        """Resets the object to zero."""
        self.name = ""
        self.settings.clear()
        self.version = 1
        self._is_dirty = False


class ConfigObjectFactory(ObjectFactory[ConfigObject]):
    """Factory for configuration objects."""

    def create(self, *args, **kwargs) -> ConfigObject:
        """Creates a new configuration object."""
        name = args[0] if args else kwargs.get("name", "default")
        initial_settings = kwargs.get("settings", {})

        config_obj = ConfigObject(name=name)
        config_obj.settings.update(initial_settings)
        return config_obj

    def reset(self, obj: ConfigObject) -> bool:
        """Resets the configuration object to zero."""
        try:
            obj.reset()
            return True
        except (AttributeError, TypeError):
            return False

    def validate(self, obj: ConfigObject) -> bool:
        """Validates a configuration object."""
        try:
            return obj.is_valid()
        except (AttributeError, TypeError):
            return False

    def get_key(self, *args, **kwargs) -> str:
        """Generates a key based on the configuration type."""
        name = args[0] if args else kwargs.get("name", "default")
        # Group by configuration type
        config_type = name.split("_")[0] if "_" in name else "general"
        return f"config_{config_type}"

    def estimate_size(self, obj: ConfigObject) -> int:
        """Estimates the size of the configuration object."""
        base_size = sys.getsizeof(obj)
        settings_size = sys.getsizeof(obj.settings)

        # Add the approximate size of the settings content
        for key, value in obj.settings.items():
            settings_size += sys.getsizeof(key) + sys.getsizeof(value)

        return base_size + settings_size


# === Example 2: Factory for network buffers ===


class NetworkBuffer:
    """Reusable network buffer with metadata."""

    def __init__(self, size: int):
        self.size = size
        self.data = bytearray(size)
        self.position = 0
        self.marked_position = 0
        self.protocol = None
        self.timestamp = time.time()

    def write(self, data: bytes) -> int:
        """Writes data to the buffer."""
        if self.position + len(data) > self.size:
            raise BufferError("Buffer overflow")

        self.data[self.position : self.position + len(data)] = data
        old_position = self.position
        self.position += len(data)
        return old_position

    def read(self, length: int = None) -> bytes:
        """Reads data from the buffer."""
        if length is None:
            length = self.position

        if self.marked_position + length > self.position:
            raise BufferError("Not enough data")

        data = bytes(self.data[self.marked_position : self.marked_position + length])
        self.marked_position += length
        return data

    def reset(self):
        """Resets the buffer to zero."""
        self.position = 0
        self.marked_position = 0
        self.protocol = None
        self.timestamp = time.time()
        # Optional: clean the content
        self.data[:] = bytearray(self.size)

    def is_valid(self) -> bool:
        """Checks if the buffer is valid."""
        return (
            isinstance(self.data, bytearray)
            and len(self.data) == self.size
            and 0 <= self.position <= self.size
            and 0 <= self.marked_position <= self.position
        )


class NetworkBufferFactory(ObjectFactory[NetworkBuffer]):
    """Factory for network buffers."""

    def create(self, *args, **kwargs) -> NetworkBuffer:
        """Creates a new network buffer."""
        size = args[0] if args else kwargs.get("size", 4096)
        protocol = kwargs.get("protocol", None)

        buffer = NetworkBuffer(size)
        buffer.protocol = protocol
        return buffer

    def reset(self, obj: NetworkBuffer) -> bool:
        """Resets the network buffer to zero."""
        try:
            obj.reset()
            return True
        except (AttributeError, TypeError, BufferError):
            return False

    def validate(self, obj: NetworkBuffer) -> bool:
        """Validates a network buffer."""
        try:
            return obj.is_valid()
        except (AttributeError, TypeError):
            return False

    def get_key(self, *args, **kwargs) -> str:
        """Generates a key based on size and protocol."""
        size = args[0] if args else kwargs.get("size", 4096)
        protocol = kwargs.get("protocol", "generic")

        # Group by size ranges (powers of 2)
        size_bucket = 1 << (size - 1).bit_length()  # Next power of 2

        return f"netbuf_{protocol}_{size_bucket}"

    def estimate_size(self, obj: NetworkBuffer) -> int:
        """Estimates the size of the network buffer."""
        base_size = sys.getsizeof(obj)
        data_size = sys.getsizeof(obj.data)
        return base_size + data_size

    def destroy(self, obj: NetworkBuffer) -> None:
        """Cleans up the network buffer."""
        try:
            # Clean sensitive data if necessary
            obj.data[:] = bytearray(obj.size)
        except (AttributeError, TypeError):
            pass


# === Example 3: Factory for computation caches ===


class ComputationCache:
    """Cache for expensive computation results."""

    def __init__(self, max_entries: int = 100):
        self.max_entries = max_entries
        self.cache: Dict[str, Any] = {}
        self.access_count: Dict[str, int] = {}
        self.created_at = time.time()

    def get(self, key: str) -> Any:
        """Retrieves a value from the cache."""
        if key in self.cache:
            self.access_count[key] = self.access_count.get(key, 0) + 1
            return self.cache[key]
        return None

    def put(self, key: str, value: Any):
        """Stores a value in the cache."""
        if len(self.cache) >= self.max_entries:
            # Remove the least used entry
            least_used = min(self.access_count.items(), key=lambda x: x[1])
            del self.cache[least_used[0]]
            del self.access_count[least_used[0]]

        self.cache[key] = value
        self.access_count[key] = 1

    def clear(self):
        """Clears the cache."""
        self.cache.clear()
        self.access_count.clear()

    def is_valid(self) -> bool:
        """Checks if the cache is valid."""
        return (
            isinstance(self.cache, dict)
            and isinstance(self.access_count, dict)
            and len(self.cache) == len(self.access_count)
        )


class ComputationCacheFactory(ObjectFactory[ComputationCache]):
    """Factory for computation caches."""

    def create(self, *args, **kwargs) -> ComputationCache:
        """Creates a new computation cache."""
        max_entries = args[0] if args else kwargs.get("max_entries", 100)
        return ComputationCache(max_entries)

    def reset(self, obj: ComputationCache) -> bool:
        """Resets the cache to zero."""
        try:
            obj.clear()
            return True
        except (AttributeError, TypeError):
            return False

    def validate(self, obj: ComputationCache) -> bool:
        """Validates a computation cache."""
        try:
            return obj.is_valid()
        except (AttributeError, TypeError):
            return False

    def get_key(self, *args, **kwargs) -> str:
        """Generates a key based on the cache size."""
        max_entries = args[0] if args else kwargs.get("max_entries", 100)

        # Group by size ranges
        if max_entries <= 50:
            size_category = "small"
        elif max_entries <= 200:
            size_category = "medium"
        else:
            size_category = "large"

        return f"cache_{size_category}"

    def estimate_size(self, obj: ComputationCache) -> int:
        """Estimates the size of the cache."""
        base_size = sys.getsizeof(obj)
        cache_size = sys.getsizeof(obj.cache)
        access_size = sys.getsizeof(obj.access_count)

        # Add the approximate size of the content
        for key, value in obj.cache.items():
            cache_size += sys.getsizeof(key) + sys.getsizeof(value)

        for key, count in obj.access_count.items():
            access_size += sys.getsizeof(key) + sys.getsizeof(count)

        return base_size + cache_size + access_size


# === Custom factory tests ===


def test_config_factory():
    """Tests the configuration factory."""

    print("=== Test ConfigObjectFactory ===\n")

    factory = ConfigObjectFactory()
    pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

    try:
        print("--- Basic test ---")

        # Create configurations of different types
        with pool.acquire_context("database_config") as db_config:
            db_config.set_setting("host", "localhost")
            db_config.set_setting("port", 5432)
            db_config.set_setting("database", "myapp")
            print(f"DB Config: {db_config.name}, {len(db_config.settings)} settings")

        with pool.acquire_context("cache_config") as cache_config:
            cache_config.set_setting("type", "redis")
            cache_config.set_setting("ttl", 3600)
            print(f"Cache Config: {cache_config.name}, {len(cache_config.settings)} settings")

        # Reuse test
        with pool.acquire_context("database_config") as db_config2:
            # Should be reused and reset
            print(f"Reused DB Config: {len(db_config2.settings)} settings (should be 0)")
            db_config2.set_setting("host", "production-server")
            print(f"New host: {db_config2.get_setting('host')}")

        # Statistics
        stats = pool.get_basic_stats()
        print("\nStatistics:")
        print(f"  Creates: {stats['counters'].get('creates', 0)}")
        print(f"  Reuses: {stats['counters'].get('reuses', 0)}")
        hits = stats["counters"].get("hits", 0)
        misses = stats["counters"].get("misses", 0)
        total = hits + misses
        hit_rate = (hits / total) if total else 0.0
        print(f"  Hit rate: {hit_rate:.2%}")

        # See generated keys
        detailed_stats = pool.get_detailed_stats()
        print("\nKeys in pool:")
        for key in detailed_stats["by_key"]:
            print(f"  {key}")

    finally:
        pool.shutdown()


def test_network_buffer_factory():
    """Tests the network buffer factory."""

    print("\n=== Test NetworkBufferFactory ===\n")

    factory = NetworkBufferFactory()
    config = MemoryConfig(
        max_objects_per_key=8,  # Few network buffers (they are large)
        ttl_seconds=600.0,  # 10 minutes
        enable_performance_metrics=True,
    )
    pool = SmartObjectManager(factory, default_config=config)

    try:
        print("--- Network protocols test ---")

        # HTTP Buffer
        with pool.acquire_context(4096, protocol="http") as http_buf:
            http_buf.write(b"GET /api/users HTTP/1.1\r\n")
            http_buf.write(b"Host: api.example.com\r\n\r\n")
            print(f"HTTP Buffer: {http_buf.size} bytes, position {http_buf.position}")

        # TCP Buffer
        with pool.acquire_context(8192, protocol="tcp") as tcp_buf:
            tcp_buf.write(b"Binary TCP data here")
            print(f"TCP Buffer: {tcp_buf.size} bytes, protocol {tcp_buf.protocol}")

        # UDP Buffer (smaller)
        with pool.acquire_context(1500, protocol="udp") as udp_buf:
            udp_buf.write(b"UDP packet data")
            print(f"UDP Buffer: {udp_buf.size} bytes")

        # Reuse test with same protocol and similar size
        with pool.acquire_context(4096, protocol="http") as http_buf2:
            # Should reuse the HTTP buffer
            print(f"Reused HTTP Buffer: position {http_buf2.position} (should be 0)")

            # Read/write test
            http_buf2.write(b"POST /api/data HTTP/1.1\r\n")
            data = http_buf2.read(4)
            print(f"Read data: {data}")

        # Performance with many buffers
        print("\n--- Performance test ---")

        start_time = time.time()

        for i in range(50):
            protocol = ["http", "tcp", "udp"][i % 3]
            size = [1500, 4096, 8192][i % 3]

            with pool.acquire_context(size, protocol=protocol) as buf:
                buf.write(f"Data {i}".encode())

        perf_time = time.time() - start_time

        print(f"50 operations in {perf_time * 1000:.2f}ms")

        # Metrics
        if pool.performance_metrics:
            snapshot = pool.performance_metrics.create_snapshot()
            print(f"Hit rate: {snapshot.hit_rate:.2%}")
            print(f"Average time: {snapshot.avg_acquisition_time_ms:.2f}ms")

    finally:
        pool.shutdown()


def test_computation_cache_factory():
    """Tests the computation cache factory."""

    print("\n=== Test ComputationCacheFactory ===\n")

    factory = ComputationCacheFactory()
    pool = SmartObjectManager(factory, preset=MemoryPreset.DATABASE_CONNECTIONS)

    try:
        print("--- Computation cache test ---")

        # Cache for math calculations
        with pool.acquire_context(50) as math_cache:
            # Simulate expensive calculations
            for i in range(10):
                key = f"fibonacci_{i}"
                # Simulate Fibonacci calculation
                if i <= 1:
                    value = i
                else:
                    # In reality, we would do the calculation
                    value = i * 2  # Simplified simulation

                math_cache.put(key, value)

            print(f"Math cache: {len(math_cache.cache)} entries")

            # Retrieval test
            fib_5 = math_cache.get("fibonacci_5")
            print(f"fibonacci_5 = {fib_5}")

        # Cache for API requests
        with pool.acquire_context(100) as api_cache:
            # Simulate API responses
            for i in range(5):
                key = f"user_{i}"
                value = {"id": i, "name": f"User {i}", "email": f"user{i}@example.com"}
                api_cache.put(key, value)

            print(f"API cache: {len(api_cache.cache)} entries")

            # Retrieval test
            user_2 = api_cache.get("user_2")
            print(f"user_2 = {user_2}")

        # Reuse test (same size -> same key)
        with pool.acquire_context(50) as math_cache2:
            # Should reuse the previous cache (reset)
            print(f"Reused math cache: {len(math_cache2.cache)} entries (should be 0)")

        # Test with large cache
        print("\n--- Large cache test ---")

        with pool.acquire_context(500) as big_cache:  # Large size -> different key
            # Fill with a lot of data
            for i in range(100):
                big_cache.put(f"item_{i}", f"value_{i}")

            print(f"Big cache: {len(big_cache.cache)} entries")

        # Detailed statistics
        detailed_stats = pool.get_detailed_stats()
        print("\n--- Statistics by size ---")

        for key, stats in detailed_stats["by_key"].items():
            print(f"{key}: {stats['pooled_count']} caches, {stats['memory_bytes'] / 1024:.1f} KB")

    finally:
        pool.shutdown()


def test_performance_comparison():
    """Performance comparison between the different factories."""

    print("\n=== Performance Comparison ===\n")

    factories = [
        ("Config", ConfigObjectFactory()),
        ("Network", NetworkBufferFactory()),
        ("Cache", ComputationCacheFactory()),
    ]

    for name, factory in factories:
        print(f"--- Test {name} Factory ---")

        pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

        try:
            start_time = time.time()

            # Standardized test for each factory
            for i in range(100):
                if name == "Config":
                    with pool.acquire_context(f"test_config_{i % 5}") as obj:
                        obj.set_setting("key", f"value_{i}")
                elif name == "Network":
                    with pool.acquire_context(4096, protocol="test") as obj:
                        obj.write(f"data_{i}".encode())
                elif name == "Cache":
                    with pool.acquire_context(100) as obj:
                        obj.put(f"key_{i}", f"value_{i}")

            test_time = time.time() - start_time
            stats = pool.get_basic_stats()

            print(f"  Time: {test_time * 1000:.2f}ms")
            hits = stats["counters"].get("hits", 0)
            misses = stats["counters"].get("misses", 0)
            total = hits + misses
            hit_rate = (hits / total) if total else 0.0
            print(f"  Hit rate: {hit_rate:.2%}")
            print(f"  Creates: {stats['counters'].get('creates', 0)}")
            print(f"  Reuses: {stats['counters'].get('reuses', 0)}")

        finally:
            pool.shutdown()

        print()


if __name__ == "__main__":
    test_config_factory()
    test_network_buffer_factory()
    test_computation_cache_factory()
    test_performance_comparison()
