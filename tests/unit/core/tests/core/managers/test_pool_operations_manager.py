"""Tests for the PoolOperationsManager class."""

import logging
import time
from collections import deque
from unittest.mock import Mock, patch

from smartpool.config import MemoryConfig
from smartpool.core.managers.pool_operations_manager import PoolOperationsManager
from smartpool.core.smartpool_manager import PooledObject


# pylint: disable=protected-access, W0201, R0903
class BaseTestPoolOperationsManager:
    """Base class for PoolOperationsManager tests."""

    def setup_method(self):
        """Set up for each test method."""
        self.mock_pool = Mock()
        self.mock_pool.logger = Mock()
        self.mock_pool.stats = Mock()
        self.mock_pool.factory = Mock()
        self.mock_pool.get_config_for_key.return_value = MemoryConfig()
        self.manager = PoolOperationsManager(self.mock_pool)


class TestCorruptionHandling(BaseTestPoolOperationsManager):
    """Tests related to object corruption handling."""

    def test_mark_as_corrupted_threshold_reached(self):
        """Test that _mark_as_corrupted logs an error when the threshold is reached."""
        mock_pooled_obj = PooledObject(
            obj=Mock(), created_at=time.time(), last_accessed=time.time()
        )
        key = "test_key"
        config = MemoryConfig(max_corrupted_objects=2)
        self.mock_pool.get_config_for_key.return_value = config

        # Mock the logger
        with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
            # Mark as corrupted once
            self.manager._mark_as_corrupted(key, mock_pooled_obj)
            assert self.manager._corrupted_objects[key] == 1
            mock_safe_log.assert_not_called()

            # Mark as corrupted again, reaching the threshold
            self.manager._mark_as_corrupted(key, mock_pooled_obj)
            assert self.manager._corrupted_objects[key] == 2
            mock_safe_log.assert_called_once_with(
                self.manager.logger,
                logging.ERROR,
                f"High number of corrupted objects ({self.manager._corrupted_objects[key]}) "
                f"for key {key}. Consider investigating the factory.",
            )

    def test_cleanup_corruption_stats(self):
        """Test that cleanup_corruption_stats removes older entries."""
        self.manager._corrupted_objects = {f"key{i}": 1 for i in range(1, 10)}
        self.manager._corrupted_objects["key10"] = 1

        removed_count = self.manager.cleanup_corruption_stats(max_keys=5)

        assert removed_count == 5
        assert len(self.manager._corrupted_objects) == 5
        assert "key1" not in self.manager._corrupted_objects
        assert "key6" in self.manager._corrupted_objects

    def test_cleanup_corruption_stats_no_cleanup_needed(self):
        """Test cleanup_corruption_stats when no cleanup is needed."""
        self.manager._corrupted_objects = {"key1": 1, "key2": 2}
        removed_count = self.manager.cleanup_corruption_stats(max_keys=5)
        assert removed_count == 0

    def test_cleanup_corruption_stats_empty_dict(self):
        """Test cleanup_corruption_stats with empty corruption dict to cover line 334."""
        # Start with empty corruption dict
        self.manager._corrupted_objects = {}

        removed_count = self.manager.cleanup_corruption_stats(max_keys=5)

        # Should return 0 since no cleanup is needed
        assert removed_count == 0

    def test_get_corruption_stats(self):
        """Test get_corruption_stats returns a copy of the stats."""
        self.manager._corrupted_objects = {"key_a": 5, "key_b": 10}
        stats = self.manager.get_corruption_stats()
        assert stats == {"key_a": 5, "key_b": 10}
        # Ensure it's a copy
        stats["key_a"] = 0
        assert self.manager._corrupted_objects["key_a"] == 5

    def test_find_object_fails_validation_and_is_corrupted(self):
        """Test that an object failing validation repeatedly is marked as corrupted."""
        # Use a single object that will fail validation multiple times
        mock_pooled_obj = PooledObject(
            obj=Mock(), created_at=time.time(), last_accessed=time.time()
        )
        pool_data = {"key1": deque([mock_pooled_obj])}
        self.mock_pool.factory.validate.return_value = False
        config = MemoryConfig(max_validation_attempts=3)

        # Mock get_config_for_key to return our config
        self.mock_pool.get_config_for_key.return_value = config

        with patch.object(self.manager, "_mark_as_corrupted") as mock_mark_corrupted:
            result = self.manager.find_valid_object_with_retry(
                "key1", time.time(), config, pool_data
            )

            assert not result.success
            # The same object should be validated 3 times and then marked as corrupted
            assert self.mock_pool.factory.validate.call_count == 3
            mock_mark_corrupted.assert_called_once_with("key1", mock_pooled_obj)


class TestObjectValidationAndReset(BaseTestPoolOperationsManager):
    """Tests related to object validation and reset."""

    def test_validate_and_reset_object_validation_exception(self):
        """Test that validate_and_reset_object handles exceptions during validation."""
        self.mock_pool.factory.validate.side_effect = RuntimeError("Validation Error")
        mock_obj = Mock()

        with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
            is_valid = self.manager.validate_and_reset_object(mock_obj, "key1", MemoryConfig())

            assert not is_valid
            mock_safe_log.assert_called_once_with(
                self.manager.logger,
                logging.WARNING,
                "Exception during object validation for key key1:"
                " Validation Error. Destroying object.",
            )
            self.mock_pool.factory.destroy.assert_called_once_with(mock_obj)

    def test_validate_and_reset_object_reset_exception(self):
        """Test that validate_and_reset_object handles exceptions during reset."""
        self.mock_pool.factory.validate.return_value = True
        self.mock_pool.factory.reset.side_effect = RuntimeError("Reset Error")
        mock_obj = Mock()

        with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
            is_valid = self.manager.validate_and_reset_object(mock_obj, "key1", MemoryConfig())

            assert not is_valid
            self.mock_pool.stats.increment.assert_any_call("reset_failures")
            self.mock_pool.stats.increment.assert_any_call("destroys")
            assert self.mock_pool.stats.increment.call_count == 2
            mock_safe_log.assert_called_once_with(
                self.manager.logger,
                logging.WARNING,
                "Exception during object reset for key key1: Reset Error. Destroying object.",
            )
            self.mock_pool.factory.destroy.assert_called_once_with(mock_obj)

    def test_validate_and_reset_object_success(self):
        """Test successful validation and reset of an object."""
        self.mock_pool.factory.validate.return_value = True
        self.mock_pool.factory.reset.return_value = True
        is_valid = self.manager.validate_and_reset_object(Mock(), "key1", MemoryConfig())
        assert is_valid

    def test_validate_and_reset_object_fails_validation(self):
        """Test when an object fails validation."""
        self.mock_pool.factory.validate.return_value = False
        mock_obj = Mock()

        with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
            is_valid = self.manager.validate_and_reset_object(mock_obj, "key1", MemoryConfig())

            assert not is_valid
            self.mock_pool.stats.increment.assert_any_call("validation_failures")
            self.mock_pool.stats.increment.assert_any_call("destroys")
            assert self.mock_pool.stats.increment.call_count == 2
            mock_safe_log.assert_called_once_with(
                self.manager.logger,
                logging.WARNING,
                "Object validation failed for key key1. Destroying object.",
            )
            self.mock_pool.factory.destroy.assert_called_once_with(mock_obj)

    def test_validate_and_reset_object_fails_reset(self):
        """Test when an object fails the reset process."""
        self.mock_pool.factory.validate.return_value = True
        self.mock_pool.factory.reset.return_value = False
        mock_obj = Mock()

        with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
            is_valid = self.manager.validate_and_reset_object(mock_obj, "key1", MemoryConfig())

            assert not is_valid
            self.mock_pool.stats.increment.assert_any_call("reset_failures")
            self.mock_pool.stats.increment.assert_any_call("destroys")
            assert self.mock_pool.stats.increment.call_count == 2
            mock_safe_log.assert_called_once_with(
                self.manager.logger,
                logging.WARNING,
                "Object reset failed for key key1. Destroying object.",
            )
            self.mock_pool.factory.destroy.assert_called_once_with(mock_obj)


class TestPoolAddition(BaseTestPoolOperationsManager):
    """Tests related to adding objects to the pool."""

    def test_add_to_pool(self):
        """Test adding a valid object to the pool."""
        pool_data = {}
        mock_obj = Mock()
        self.mock_pool.factory.estimate_size.return_value = 100

        with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
            added = self.manager.add_to_pool("key1", mock_obj, MemoryConfig(), pool_data)

            assert added
            assert "key1" in pool_data
            assert len(pool_data["key1"]) == 1
            assert isinstance(pool_data["key1"][0], PooledObject)
            mock_safe_log.assert_called_once_with(
                self.manager.logger, logging.DEBUG, "Object returned to pool for key key1"
            )

    def test_add_to_pool_when_key_pool_is_full(self):
        """Test that an object is destroyed if its specific key queue is full."""
        pool_data = {"key1": deque([Mock(), Mock()])}
        config = MemoryConfig(max_objects_per_key=2)
        mock_obj = Mock()

        with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
            added = self.manager.add_to_pool("key1", mock_obj, config, pool_data)

            assert not added
            assert len(pool_data["key1"]) == 2
            self.mock_pool.factory.destroy.assert_called_once_with(mock_obj)
            mock_safe_log.assert_called_once_with(
                self.manager.logger,
                logging.INFO,
                (
                    "Pool for key key1 is full "
                    f"(max_objects_per_key={config.max_objects_per_key}), destroying object."
                ),
            )


class TestEvictionAndCleanup(BaseTestPoolOperationsManager):
    """Tests related to object eviction and cleanup."""

    def test_should_add_to_pool_triggers_eviction(self):
        """Test that should_add_to_pool triggers LRU eviction when max_total_objects is reached."""
        # Setup a pool with more objects than max_total_objects to trigger eviction
        pool_data = {
            "key1": deque(
                [
                    PooledObject(obj=Mock(), created_at=time.time(), last_accessed=time.time())
                    for _ in range(5)
                ]
            ),
            "key2": deque(
                [
                    PooledObject(obj=Mock(), created_at=time.time(), last_accessed=time.time())
                    for _ in range(5)
                ]
            ),
        }
        # Simulate access order for LRU
        self.manager.update_key_access("key1", time.time() - 10)
        self.manager.update_key_access("key2", time.time() - 5)

        max_total_objects = 8  # Current total is 10, so eviction needed

        # Mock evict_least_recently_used and simulate actual pool modification
        def mock_evict(pool_data_arg):
            # Simulate removal of 3 objects from key1 to make space
            while len(pool_data_arg["key1"]) > 2:
                pool_data_arg["key1"].popleft()
            return 3

        with patch.object(
            self.manager, "evict_least_recently_used", side_effect=mock_evict
        ) as mock_evict:
            with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
                can_add = self.manager.should_add_to_pool(pool_data, max_total_objects)

                mock_evict.assert_called_once_with(pool_data)
                assert can_add  # After eviction, there should be space (7 < 8)
                mock_safe_log.assert_called_with(
                    self.manager.logger, logging.INFO, "LRU eviction: removed 3 objects"
                )

    def test_should_add_to_pool_no_eviction_needed(self):
        """Test should_add_to_pool when no eviction is needed."""
        pool_data = {
            "key1": deque(
                [
                    PooledObject(obj=Mock(), created_at=time.time(), last_accessed=time.time())
                    for _ in range(3)
                ]
            )
        }
        max_total_objects = 5

        can_add = self.manager.should_add_to_pool(pool_data, max_total_objects)
        assert can_add

    def test_evict_least_recently_used_empties_queue_and_removes_key(self):
        """Test that evict_least_recently_used empties a queue and removes its key."""
        mock_obj = Mock()
        pool_data = {
            "lru_key": deque(
                [PooledObject(obj=mock_obj, created_at=time.time(), last_accessed=time.time())]
            ),
            "mru_key": deque(
                [PooledObject(obj=Mock(), created_at=time.time(), last_accessed=time.time())]
            ),
        }
        self.manager.update_key_access("lru_key", time.time() - 10)
        self.manager.update_key_access("mru_key", time.time() - 5)

        # Evict enough to empty 'lru_key'
        evicted_count = self.manager.evict_least_recently_used(pool_data)

        assert evicted_count == 1
        assert "lru_key" not in pool_data
        assert "lru_key" not in self.manager._key_access_order
        self.mock_pool.factory.destroy.assert_called_once_with(mock_obj)

    def test_evict_least_recently_used_no_keys(self):
        """Test evict_least_recently_used with no keys in access order."""
        pool_data = {}
        evicted_count = self.manager.evict_least_recently_used(pool_data)
        assert evicted_count == 0

    def test_cleanup_expired_objects(self):
        """Test that cleanup_expired_objects removes expired objects and updates stats."""
        expired_obj = PooledObject(
            obj=Mock(), created_at=time.time() - 100, last_accessed=time.time()
        )
        valid_obj = PooledObject(obj=Mock(), created_at=time.time() - 10, last_accessed=time.time())
        pool_data = {"key1": deque([expired_obj, valid_obj]), "key2": deque([expired_obj])}
        config = MemoryConfig(ttl_seconds=50)
        self.mock_pool.get_config_for_key.return_value = config

        # Ensure key2 is in _key_access_order so the cleanup will test that condition
        self.manager.update_key_access("key2", time.time() - 20)

        with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
            expired_count = self.manager.cleanup_expired_objects(pool_data, time.time())

            assert expired_count == 2
            assert len(pool_data["key1"]) == 1
            assert valid_obj in pool_data["key1"]
            assert "key2" not in pool_data
            # Verify key2 was also removed from _key_access_order
            assert "key2" not in self.manager._key_access_order
            assert self.mock_pool.factory.destroy.call_count == 2
            self.mock_pool.stats.increment.assert_called_with("expired", 2)
            mock_safe_log.assert_called_with(
                self.manager.logger, logging.INFO, "Cleanup: removed 2 expired objects"
            )

    def test_cleanup_expired_objects_no_expired(self):
        """Test cleanup_expired_objects when no objects are expired."""
        valid_obj = PooledObject(obj=Mock(), created_at=time.time() - 10, last_accessed=time.time())
        pool_data = {"key1": deque([valid_obj])}
        config = MemoryConfig(ttl_seconds=50)
        self.mock_pool.get_config_for_key.return_value = config

        with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
            expired_count = self.manager.cleanup_expired_objects(pool_data, time.time())

            assert expired_count == 0
            mock_safe_log.assert_not_called()

    def test_lru_eviction(self):
        """Test that the least recently used items are evicted when the pool is full."""
        pool_data = {
            "lru_key": deque(
                [PooledObject(obj=Mock(), created_at=time.time(), last_accessed=time.time())]
            ),
            "mru_key": deque(
                [PooledObject(obj=Mock(), created_at=time.time(), last_accessed=time.time())]
            ),
        }
        # Simulate access order
        self.manager.update_key_access("lru_key", time.time() - 10)
        self.manager.update_key_access("mru_key", time.time() - 5)

        # Evict one object
        evicted_count = self.manager.evict_least_recently_used(pool_data)

        assert evicted_count == 1
        assert "lru_key" not in pool_data
        assert "mru_key" in pool_data
        self.mock_pool.stats.increment.assert_called_with("evictions")


class TestObjectFindingAndRetry(BaseTestPoolOperationsManager):
    """Tests related to finding and retrying objects."""

    def test_find_valid_object_success(self):
        """Test finding a valid, non-expired object in the pool."""
        mock_pooled_obj = PooledObject(
            obj=Mock(), created_at=time.time(), last_accessed=time.time()
        )
        pool_data = {"key1": deque([mock_pooled_obj])}
        self.mock_pool.factory.validate.return_value = True

        result = self.manager.find_valid_object_with_retry(
            "key1", time.time(), MemoryConfig(), pool_data
        )

        assert result.success
        assert result.object_found is mock_pooled_obj
        self.mock_pool.factory.validate.assert_called_once_with(mock_pooled_obj.obj)

    def test_find_valid_object_key_not_in_pool(self):
        """Test finding object when key is not in pool."""
        pool_data = {}
        result = self.manager.find_valid_object_with_retry(
            "missing_key", time.time(), MemoryConfig(), pool_data
        )

        assert not result.success
        assert result.error_message == "Key not in pool"

    def test_find_object_is_expired(self):
        """Test that an expired object is identified and destroyed."""
        mock_pooled_obj = PooledObject(
            obj=Mock(), created_at=time.time() - 100, last_accessed=time.time()
        )
        pool_data = {"key1": deque([mock_pooled_obj])}
        config = MemoryConfig(ttl_seconds=50)

        result = self.manager.find_valid_object_with_retry("key1", time.time(), config, pool_data)

        assert not result.success
        self.mock_pool.stats.increment.assert_any_call("expired")
        self.mock_pool.stats.increment.assert_any_call("destroys")
        assert self.mock_pool.stats.increment.call_count == 2
        self.mock_pool.factory.destroy.assert_called_once_with(mock_pooled_obj.obj)

    def test_find_object_validation_exception(self):
        """Test validation exception during find_valid_object_with_retry."""
        mock_pooled_obj = PooledObject(
            obj=Mock(), created_at=time.time(), last_accessed=time.time()
        )
        pool_data = {"key1": deque([mock_pooled_obj])}
        self.mock_pool.factory.validate.side_effect = RuntimeError("Validation error")

        result = self.manager.find_valid_object_with_retry(
            "key1", time.time(), MemoryConfig(), pool_data
        )

        assert not result.success

    def test_find_object_requeue_after_validation_failure(self):
        """Test that objects are requeued after validation failure if attempts remain."""
        mock_pooled_obj = PooledObject(
            obj=Mock(), created_at=time.time(), last_accessed=time.time()
        )
        pool_data = {"key1": deque([mock_pooled_obj])}

        # First call fails validation, second succeeds
        self.mock_pool.factory.validate.side_effect = [False, True]
        config = MemoryConfig(max_validation_attempts=3)

        result = self.manager.find_valid_object_with_retry("key1", time.time(), config, pool_data)

        # Should eventually succeed after requeue
        assert result.success
        assert self.mock_pool.factory.validate.call_count == 2
        # Check that validation_failures was incremented and then reset
        assert mock_pooled_obj.validation_failures == 0

    def test_validate_pooled_object_requeue_scenario(self):
        """Test the specific requeue scenario in _validate_pooled_object to cover lines 171-172."""
        mock_pooled_obj = PooledObject(
            obj=Mock(), created_at=time.time(), last_accessed=time.time()
        )
        queue = deque()

        # Mock validation to fail
        self.mock_pool.factory.validate.return_value = False
        config = MemoryConfig(max_validation_attempts=3)
        self.mock_pool.get_config_for_key.return_value = config

        # Call the method directly
        result = self.manager._validate_pooled_object(mock_pooled_obj, "test_key", queue)

        # Should fail and object should be requeued
        assert not result.success
        assert result.error_message == "Validation failed, object requeued"
        assert len(queue) == 1  # Object was requeued
        assert mock_pooled_obj.validation_failures == 1
        self.mock_pool.stats.increment.assert_called_with("validation_failures")


class TestUtilityAndDestruction(BaseTestPoolOperationsManager):
    """Tests for utility methods and object destruction."""

    def test_try_destroy_object_exception(self):
        """Test _try_destroy_object handles exceptions gracefully."""
        self.mock_pool.factory.destroy.side_effect = RuntimeError("Destroy error")
        mock_obj = Mock()

        with patch("smartpool.core.managers.pool_operations_manager.safe_log") as mock_safe_log:
            self.manager._try_destroy_object(mock_obj)
            mock_safe_log.assert_called_once_with(
                self.manager.logger, logging.WARNING, "Failed to destroy object: Destroy error"
            )

    def test_clear_all_data(self):
        """Test clearing all data structures and destroying objects."""
        pool_data = {
            "key1": deque(
                [PooledObject(obj=Mock(), created_at=time.time(), last_accessed=time.time())]
            ),
            "key2": deque(
                [PooledObject(obj=Mock(), created_at=time.time(), last_accessed=time.time())]
            ),
        }
        self.manager.update_key_access("key1", time.time())
        self.manager._corrupted_objects["key1"] = 1

        destroyed_count = self.manager.clear_all_data(pool_data)

        assert destroyed_count == 2
        assert len(pool_data) == 0
        assert len(self.manager._key_access_order) == 0
        assert len(self.manager._corrupted_objects) == 0
        assert self.mock_pool.factory.destroy.call_count == 2

    def test_get_lru_stats(self):
        """Test get_lru_stats returns a copy of the LRU order."""
        self.manager.update_key_access("key_x", 1.0)
        self.manager.update_key_access("key_y", 2.0)
        stats = self.manager.get_lru_stats()
        assert stats == {"key_x": 1.0, "key_y": 2.0}
        # Ensure it's a copy
        stats["key_x"] = 0.0
        assert self.manager._key_access_order["key_x"] == 1.0
