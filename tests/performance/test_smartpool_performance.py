"""
Performance tests for the SmartObjectManager.
These tests measure the time taken for key operations like acquire and release.
"""

import pytest

from examples.factories import BytesIOFactory
from smartpool import SmartObjectManager
from smartpool.config import MemoryConfig, PoolConfiguration


class TestSmartPoolPerformance:
    """
    Performance tests for SmartObjectManager using pytest-benchmark.
    """

    @pytest.fixture(scope="class")
    def large_bytesio_pool(self):
        """Provide a SmartObjectManager+BytesIOFactory fixture for performance tests."""
        factory = BytesIOFactory()
        # Use a larger pool size for performance testing
        config = MemoryConfig(max_objects_per_key=1000, ttl_seconds=300)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )
        yield pool
        pool.shutdown()

    def test_acquire_release_performance(self, large_bytesio_pool, benchmark):
        """
        Measure the performance of acquiring and releasing objects from the pool.
        """
        # Pre-fill the pool to ensure objects are available for reuse
        # This helps measure the overhead of acquire/release, not creation
        pre_acquired = []
        for _ in range(large_bytesio_pool.default_config.max_objects_per_key):
            obj_id, key, obj = large_bytesio_pool.acquire()
            pre_acquired.append((obj_id, key, obj))
        for obj_id, key, obj in pre_acquired:
            large_bytesio_pool.release(obj_id, key, obj)

        # Benchmark the acquire-release cycle
        def acquire_release():
            obj_id, key, obj = large_bytesio_pool.acquire()
            large_bytesio_pool.release(obj_id, key, obj)

        benchmark(acquire_release)

    def test_object_creation_performance(self, large_bytesio_pool, benchmark):
        """
        Measure the performance of creating new objects when the pool is exhausted.
        """
        # Exhaust the pool first
        acquired_objects = []
        for _ in range(large_bytesio_pool.default_config.max_objects_per_key):
            obj_id, key, obj = large_bytesio_pool.acquire()
            acquired_objects.append((obj_id, key, obj))

        # Benchmark creating a new object (pool miss)
        def create_new_object():
            obj_id, key, obj = large_bytesio_pool.acquire()
            large_bytesio_pool.release(obj_id, key, obj)

        benchmark(create_new_object)

        # Release all objects after benchmarking
        for obj_id, key, obj in acquired_objects:
            large_bytesio_pool.release(obj_id, key, obj)
