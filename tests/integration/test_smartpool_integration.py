"""
Integration tests for the SmartObjectManager and its interaction with a real factory.
These tests ensure that components work together as expected without mocking internal dependencies.
"""

from io import BytesIO

import pytest

from examples.factories import BytesIOFactory
from smartpool import SmartObjectManager
from smartpool.config import MemoryConfig, PoolConfiguration


class TestSmartPoolIntegration:
    """
    Integration tests for SmartObjectManager with a real BytesIOFactory.
    """

    @pytest.fixture
    def bytesio_pool(self):
        """Fixture to provide a SmartObjectManager instance with BytesIOFactory."""
        factory = BytesIOFactory()
        # Use a small pool size for integration testing to observe pooling behavior
        config = MemoryConfig(max_objects_per_key=5, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )
        yield pool
        pool.shutdown()  # Ensure the pool is shut down after tests

    def test_acquire_release_cycle(self, bytesio_pool):
        """
        Test the basic acquire-release cycle with a real factory.
        Ensures objects are acquired, used, and returned to the pool correctly.
        """
        acquired_objects = []
        # Acquire more objects than max_pool_size to test creation and pooling
        for _ in range(10):
            obj_id, key, obj = bytesio_pool.acquire()
            assert obj is not None
            assert isinstance(obj, BytesIO)  # BytesIOFactory returns BytesIO objects
            acquired_objects.append((obj_id, key, obj))

        # Release objects back to the pool
        for obj_id, key, obj in acquired_objects:
            bytesio_pool.release(obj_id, key, obj)

        # Verify pool statistics
        stats = bytesio_pool.get_basic_stats()
        assert stats["total_pooled_objects"] <= bytesio_pool.default_config.max_objects_per_key
        assert stats["active_objects_count"] == 0
        assert stats["counters"]["creates"] >= 1  # At least one object should have been created

    def test_object_reuse(self, bytesio_pool):
        """
        Test that objects are actually reused from the pool.
        Acquire, modify, release, then acquire again and check if the same object is returned.
        """
        # Acquire an object, write some data, and release
        obj_id1, key1, obj1 = bytesio_pool.acquire()
        obj1_initial_id = id(obj1)
        obj1.write(b"test data")
        bytesio_pool.release(obj_id1, key1, obj1)

        # Acquire another object for the same key
        obj_id2, key2, obj2 = bytesio_pool.acquire()

        # Verify that the same object (or a reset version of it) was reused
        # The BytesIOFactory resets the buffer; content is empty but object ID can be identical.

        assert id(obj2) == obj1_initial_id  # Should be the same Python object
        assert obj2.getvalue() == b""  # Should be reset

        bytesio_pool.release(obj_id2, key2, obj2)

    def test_pool_exhaustion_and_creation(self, bytesio_pool):
        """
        Test behavior when the pool is exhausted and new objects need to be created.
        """
        max_objects_per_key = bytesio_pool.default_config.max_objects_per_key
        acquired_first_batch = []

        # Acquire up to max_pool_size
        for _ in range(max_objects_per_key):
            obj_id, key, obj = bytesio_pool.acquire()
            acquired_first_batch.append((obj_id, key, obj))

        stats_before_exhaustion = bytesio_pool.get_basic_stats()
        assert stats_before_exhaustion["total_pooled_objects"] == 0

        # Acquire one more object - this should trigger new object creation
        obj_id_new, key_new, obj_new = bytesio_pool.acquire()
        assert obj_new is not None
        assert (obj_id_new, key_new, obj_new) not in acquired_first_batch  # Should be a new object

        stats_after_creation = bytesio_pool.get_basic_stats()
        assert stats_after_creation["counters"]["creates"] == max_objects_per_key + 1

        # Release all objects
        for obj_id, key, obj in acquired_first_batch:
            bytesio_pool.release(obj_id, key, obj)
        bytesio_pool.release(obj_id_new, key_new, obj_new)

        stats_final = bytesio_pool.get_basic_stats()
        assert stats_final["active_objects_count"] == 0
        assert (
            stats_final["total_pooled_objects"] == max_objects_per_key
        )  # Only max_objects_per_key objects are kept in pool
        assert (
            stats_final["counters"]["creates"] == max_objects_per_key + 1
        )  # One extra object was created and destroyed

    def test_pool_shutdown(self, bytesio_pool):
        """
        Test that the pool shuts down correctly, releasing all resources.
        """
        # Acquire some objects
        obj_id, key, obj = bytesio_pool.acquire()
        bytesio_pool.release(obj_id, key, obj)

        # Explicitly shut down the pool
        bytesio_pool.shutdown()

        # Verify that the pool is empty after shutdown
        stats = bytesio_pool.get_basic_stats()
        assert stats["total_pooled_objects"] == 0
        assert stats["active_objects_count"] == 0

        # Attempting to acquire after shutdown should raise an error
        with pytest.raises(Exception):  # Replace with specific PoolAlreadyShutdownError if exists
            bytesio_pool.acquire()
