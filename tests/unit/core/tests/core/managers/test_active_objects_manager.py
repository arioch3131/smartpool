"""Tests for the ActiveObjectsManager class."""

import gc
import logging
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from smartpool.core.managers import ActiveObjectsManager
from smartpool.core.utils import safe_log


# Helper class that supports weak references
# pylint: disable=R0903
class MockObject:
    """A mock object for testing weak references."""


# pylint: disable=protected-access, W0201
class TestActiveObjectsManager:
    """Tests for the ActiveObjectsManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_pool = Mock()
        self.mock_pool.logger = Mock()
        self.manager = ActiveObjectsManager(self.mock_pool)

    def test_track_and_untrack_object(self):
        """Test tracking a new active object and then untracking it."""
        obj = MockObject()  # Maintain strong reference
        obj_id = self.manager.track_active_object(obj, "test_key", 100, time.time(), 1)

        assert self.manager.get_active_count() == 1
        active_info = self.manager.get_active_objects_count_info()
        assert obj_id in active_info
        assert active_info[obj_id].key == "test_key"

        was_untracked = self.manager.untrack_active_object(obj_id)
        assert was_untracked
        assert self.manager.get_active_count() == 0
        assert obj_id not in self.manager.get_active_objects_count_info()

    def test_weakref_cleanup_on_garbage_collection(self):
        """Test that an object is automatically untracked when garbage collected."""
        obj = MockObject()

        with patch.object(
            self.manager, "_weakref_cleanup_callback", wraps=self.manager._weakref_cleanup_callback
        ) as spy_callback:
            self.manager.track_active_object(obj, "gc_key", 50, time.time(), 1)
            assert self.manager.get_active_count() == 1

            del obj  # Remove the strong reference
            gc.collect()

            spy_callback.assert_called_once()
            assert self.manager.get_active_count() == 0

    def test_cleanup_dead_weakrefs_after_callback_fails(self):
        """Test manually cleaning up if the callback somehow failed or was disabled."""
        obj = MockObject()

        # To truly test the manual cleanup, we must prevent the callback from being set.
        # We patch weakref.ref to return a weakref without the callback.
        original_ref = __import__("weakref").ref
        with patch("weakref.ref", lambda o, cb=None: original_ref(o)):
            self.manager.track_active_object(obj, "dead_ref_key", 10, time.time(), 1)

        assert len(self.manager._active_objects_count) == 1

        # Remove strong reference and run GC
        del obj
        gc.collect()

        # The weakref is now dead, and because the callback was not set, it's still in the dicts
        assert len(self.manager._active_objects_count) == 1
        assert self.manager.get_active_count() == 0  # But it reports as not living

        # Manually run the cleanup
        cleaned_count = self.manager.cleanup_dead_weakrefs()
        assert cleaned_count == 1
        assert len(self.manager._active_objects_count) == 0

    def test_get_basic_stats(self):
        """Test the statistics aggregation."""
        obj1 = MockObject()
        obj2 = MockObject()

        self.manager.track_active_object(obj1, "key1", 100, time.time(), 1)
        self.manager.track_active_object(obj2, "key2", 250, time.time(), 1)

        stats = self.manager.get_basic_stats()

        assert stats["total_tracked"] == 2
        assert stats["living_objects"] == 2
        assert stats["dead_weakrefs"] == 0
        assert stats["total_memory_bytes"] == 350

    def test_get_memory_usage_by_key(self):
        """Test memory usage aggregation by key."""
        obj1 = MockObject()
        obj2 = MockObject()
        obj3 = MockObject()
        self.manager.track_active_object(obj1, "keyA", 100, time.time(), 1)
        self.manager.track_active_object(obj2, "keyB", 200, time.time(), 1)
        self.manager.track_active_object(obj3, "keyA", 150, time.time(), 1)

        usage = self.manager.get_memory_usage_by_key()

        assert "keyA" in usage
        assert "keyB" in usage
        assert usage["keyA"]["count"] == 2
        assert usage["keyA"]["memory"] == 250
        assert usage["keyB"]["count"] == 1
        assert usage["keyB"]["memory"] == 200

    def test_info_and_usage_ignore_stale_entries_and_keep_non_weakref_objects(self):
        """Test stale metadata is ignored and non-weakref objects are still aggregated."""
        non_weakref_obj = {"not": "weakref-compatible"}
        non_weakref_id = self.manager.track_active_object(
            non_weakref_obj, "dict_key", 80, time.time(), 1
        )

        stale_obj = MockObject()
        stale_id = self.manager.track_active_object(stale_obj, "stale_key", 120, time.time(), 1)
        del self.manager._active_objects_count[stale_id]

        active_info = self.manager.get_active_objects_count_info()
        assert non_weakref_id in active_info
        assert stale_id not in active_info

        usage = self.manager.get_memory_usage_by_key()
        assert usage["dict_key"]["count"] == 1
        assert usage["dict_key"]["memory"] == 80
        assert "stale_key" not in usage

    def test_clear_all(self):
        """Test clearing all tracked objects."""
        obj1 = MockObject()
        obj2 = MockObject()
        self.manager.track_active_object(obj1, "key1", 100, time.time(), 1)
        self.manager.track_active_object(obj2, "key2", 200, time.time(), 1)

        assert self.manager.get_active_count() == 2

        cleared_count = self.manager.clear_all()
        assert cleared_count == 2
        assert self.manager.get_active_count() == 0
        assert len(self.manager._active_objects_count) == 0
        assert len(self.manager._active_objects_count_info) == 0

    def test_weakref_cleanup_callback_exception(self):
        """Test that _weakref_cleanup_callback handles exceptions during untrack."""
        obj = MockObject()
        obj_id = self.manager.track_active_object(obj, "key", 10, time.time(), 1)

        # Force untrack_active_object to raise an exception
        self.manager.untrack_active_object = MagicMock(side_effect=RuntimeError("Untrack failed"))

        # Mock the logger
        self.manager.logger = Mock()
        self.manager.logger.isEnabledFor.return_value = True

        # Call the callback directly (simulating GC)
        self.manager._weakref_cleanup_callback(None, obj_id)  # ref is not used in the callback

        self.manager.untrack_active_object.assert_called_once_with(obj_id)
        self.manager.logger.isEnabledFor.assert_called_with(logging.WARNING)
        self.manager.logger.log.assert_called_with(
            logging.WARNING, "Error in weakref cleanup: Untrack failed"
        )

    def test_safe_log_exception(self):
        """Test that _safe_log handles exceptions during logging."""
        # Force logger.log to raise an exception
        self.mock_pool.logger.isEnabledFor.return_value = True
        self.mock_pool.logger.log.side_effect = RuntimeError("Logging failed")

        # Call _safe_log
        try:
            safe_log(self.mock_pool.logger, logging.INFO, "Test message")
        except RuntimeError as e:  # Catch specific exception
            pytest.fail(f"_safe_log should not raise exceptions, but raised {e}")

    def test_safe_log_value_error_exception(self):
        """Test that _safe_log handles ValueError/OSError during logging."""
        self.manager.logger = Mock()
        self.manager.logger.isEnabledFor.return_value = True
        self.manager.logger.log.side_effect = ValueError("Logging failed")

        # Should not raise any exception
        try:
            safe_log(self.manager.logger, logging.INFO, "Test message")
        except ValueError as e:  # Catch specific exception
            pytest.fail(f"_safe_log should not raise exceptions, but raised {e}")

    def test_safe_log_general_exception(self):
        """Test that _safe_log handles general Exception during logging."""
        self.manager.logger = Mock()
        self.manager.logger.isEnabledFor.return_value = True
        self.manager.logger.log.side_effect = RuntimeError("Logging failed")

        # Should not raise any exception
        try:
            safe_log(self.manager.logger, logging.INFO, "Test message")
        except RuntimeError as e:  # Catch specific exception
            pytest.fail(f"_safe_log should not raise exceptions, but raised {e}")
