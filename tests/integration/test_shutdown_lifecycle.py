"""
Integration tests for SmartObjectManager shutdown and lifecycle scenarios.
These tests ensure proper shutdown behavior and resource cleanup.
"""

import time

import pytest

from examples.factories import BytesIOFactory
from smartpool import SmartObjectManager
from smartpool.config import MemoryConfig, PoolConfiguration
from smartpool.core.exceptions import PoolAlreadyShutdownError


class TestShutdownLifecycle:
    """
    Integration tests for SmartObjectManager shutdown and lifecycle management.
    """

    @pytest.fixture
    def bytesio_pool(self):
        """Fixture to provide a SmartObjectManager instance with BytesIOFactory."""
        factory = BytesIOFactory()
        config = MemoryConfig(max_objects_per_key=5, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )
        yield pool
        # Note: Don't auto-shutdown here as tests verify shutdown behavior

    def test_pool_shutdown_complete(self, bytesio_pool):
        """
        Test that the pool shuts down correctly, releasing all resources.
        """
        # Ensure clean state (isolate from other tests)
        bytesio_pool.active_manager.clear_all()

        # Acquire some objects - use different keys to force separate objects
        acquired_objects = []
        for i in range(3):
            obj_id, key, obj = bytesio_pool.acquire(initial_size=i * 1024)  # Force different keys
            acquired_objects.append((obj_id, key, obj))

        # Release one object back to pool
        obj_id, key, obj = acquired_objects.pop()
        bytesio_pool.release(obj_id, key, obj)

        # Verify pool has objects before shutdown
        stats_before = bytesio_pool.get_basic_stats()
        assert stats_before["total_pooled_objects"] == 1
        assert stats_before["active_objects_count"] == 2
        # Explicitly shut down the pool
        bytesio_pool.shutdown()

        # Verify that the pool is empty after shutdown
        stats_after = bytesio_pool.get_basic_stats()
        assert stats_after["total_pooled_objects"] == 0
        assert stats_after["active_objects_count"] == 0

        # Attempting to acquire after shutdown should raise an error
        with pytest.raises(PoolAlreadyShutdownError):
            bytesio_pool.acquire()

        # Attempting to release after shutdown should handle gracefully
        remaining_obj_id, remaining_key, remaining_obj = acquired_objects[0]
        # Should not raise an exception but should be handled internally
        bytesio_pool.release(remaining_obj_id, remaining_key, remaining_obj)

    def test_shutdown_with_background_cleanup(self, bytesio_pool):
        """
        Test shutdown when background cleanup is running.
        """
        # Start background cleanup
        bytesio_pool.background_manager.start_background_cleanup()

        # Add some objects to pool
        acquired_objects = []
        for _ in range(3):
            obj_id, key, obj = bytesio_pool.acquire()
            acquired_objects.append((obj_id, key, obj))

        for obj_id, key, obj in acquired_objects:
            bytesio_pool.release(obj_id, key, obj)

        # Verify background manager is running
        assert not bytesio_pool.background_manager._shutdown

        # Shutdown should stop background manager
        bytesio_pool.shutdown()

        # Verify background manager is stopped
        assert bytesio_pool.background_manager._shutdown

    def test_shutdown_idempotent(self, bytesio_pool):
        """
        Test that calling shutdown multiple times is safe.
        """
        # First shutdown
        bytesio_pool.shutdown()

        # Verify shutdown state
        with pytest.raises(PoolAlreadyShutdownError):
            bytesio_pool.acquire()

        # Second shutdown should not raise an exception
        bytesio_pool.shutdown()

        # Third shutdown should also be safe
        bytesio_pool.shutdown()

    def test_context_manager_lifecycle(self):
        """
        Test pool lifecycle when used as context manager.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(max_objects_per_key=3, ttl_seconds=60)

        with SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        ) as pool:
            # Use the pool normally
            obj_id, key, obj = pool.acquire()
            obj.write(b"test data")
            pool.release(obj_id, key, obj)

            stats = pool.get_basic_stats()
            assert stats["total_pooled_objects"] == 1

        # After context exit, pool should be shutdown
        with pytest.raises(PoolAlreadyShutdownError):
            pool.acquire()

    def test_object_lifecycle_with_ttl_expiration(self, bytesio_pool):
        """
        Test object lifecycle when TTL expires before shutdown.
        """
        # Configure shorter TTL and enable background cleanup
        bytesio_pool.default_config.ttl_seconds = 0.2
        bytesio_pool.default_config.enable_background_cleanup = True
        bytesio_pool.default_config.cleanup_interval_seconds = 0.1

        # Start background cleanup explicitly
        bytesio_pool.background_manager.start_background_cleanup()

        # Acquire and release an object
        obj_id, key, obj = bytesio_pool.acquire()
        bytesio_pool.release(obj_id, key, obj)

        # Verify object is in pool and no objects have expired yet
        stats_before = bytesio_pool.get_basic_stats()
        assert stats_before["counters"].get("expired", 0) == 0  # Use .get() to avoid KeyError
        assert stats_before["total_pooled_objects"] == 1

        # Wait for TTL to expire (wait longer to be sure)
        time.sleep(0.5)

        # Force cleanup to remove expired objects
        cleanup_result = bytesio_pool.force_cleanup()
        assert cleanup_result >= 1  # Should have cleaned up at least one expired object

        # Verify expired objects are removed
        stats_after = bytesio_pool.get_basic_stats()
        assert stats_after["total_pooled_objects"] == 0
        assert (
            stats_after["counters"].get("expired", 0) >= 1
        )  # At least one object should be marked as expired

        # Shutdown should still work correctly
        bytesio_pool.shutdown()

    def test_force_cleanup_during_shutdown(self, bytesio_pool):
        """
        Test that force_cleanup works correctly during shutdown process.
        """
        # Add objects to pool
        for _ in range(3):
            obj_id, key, obj = bytesio_pool.acquire()

        for _ in range(3):
            bytesio_pool.release(obj_id, key, obj)

        # Verify objects are pooled
        assert bytesio_pool.get_basic_stats()["total_pooled_objects"] == 3

        # Start shutdown process (but don't complete it)
        # Force cleanup should still work
        cleanup_result = bytesio_pool.force_cleanup()
        assert cleanup_result >= 0  # Should return number of cleaned objects

        # Complete shutdown
        bytesio_pool.shutdown()

        # Post-shutdown cleanup should return 0 or handle gracefully
        post_shutdown_result = bytesio_pool.force_cleanup()
        assert post_shutdown_result == 0

    def test_factory_destroy_called_on_shutdown(self, bytesio_pool):
        """
        Test that factory.destroy is called for pooled objects during shutdown.
        """
        # Create a mock factory to track destroy calls
        original_destroy = bytesio_pool.factory.destroy
        destroy_call_count = []

        def mock_destroy(obj):
            destroy_call_count.append(obj)
            return original_destroy(obj)

        bytesio_pool.factory.destroy = mock_destroy

        # Add objects to pool
        for _ in range(3):
            obj_id, key, obj = bytesio_pool.acquire()

        for _ in range(3):
            bytesio_pool.release(obj_id, key, obj)
        # Verify objects are pooled
        assert bytesio_pool.get_basic_stats()["total_pooled_objects"] == 3

        # Shutdown should call destroy on all pooled objects
        bytesio_pool.shutdown()

        # Verify destroy was called for each pooled object
        assert len(destroy_call_count) == 3

    def test_graceful_degradation_during_shutdown(self, bytesio_pool):
        """
        Test graceful degradation when operations are attempted during shutdown.
        """
        # Acquire an object
        obj_id, key, obj = bytesio_pool.acquire()

        # Start shutdown in a way that simulates partial shutdown
        bytesio_pool._shutdown_initiated = True

        # Operations should handle graceful degradation
        # Release should still work even during shutdown process
        bytesio_pool.release(obj_id, key, obj)

        # Complete shutdown
        bytesio_pool.shutdown()

        # Verify final state
        stats = bytesio_pool.get_basic_stats()
        assert stats["active_objects_count"] == 0
