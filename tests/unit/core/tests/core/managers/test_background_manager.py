"""Tests for the BackgroundManager class."""

import logging
from unittest.mock import ANY, MagicMock, Mock, patch

import pytest

from smartpool.core.exceptions import BackgroundManagerError, PoolConfigurationError
from smartpool.core.managers import BackgroundManager


# Helper class that supports weak references
# pylint: disable=R0903
class MockObject:
    """A mock object for testing weak references."""


# pylint: disable=protected-access, W0201, R0903
class BaseTestBackgroundManager:
    """Base class for BackgroundManager tests, providing common setup."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.mock_pool = Mock()
        self.mock_pool.logger = Mock()
        self.mock_pool.default_config.enable_background_cleanup = True
        self.mock_pool.default_config.cleanup_interval_seconds = 30  # seconds
        self.mock_pool.lock = MagicMock()  # Mock the context manager

        # Mock the sub-managers that the background manager calls
        self.mock_pool.operations_manager = Mock()
        self.mock_pool.operations_manager.cleanup_expired_objects.return_value = 5
        self.mock_pool.operations_manager.cleanup_corruption_stats.return_value = 0
        self.mock_pool.active_manager = Mock()
        self.mock_pool.active_manager.cleanup_dead_weakrefs.return_value = 0
        self.mock_pool.stats = Mock()

        with patch("logging.getLogger") as mock_get_logger:
            self.mock_logger = Mock()
            mock_get_logger.return_value = self.mock_logger
            self.manager = BackgroundManager(self.mock_pool)

    def teardown_method(self):
        """Tear down test fixtures after each test method."""
        self.manager.shutdown(wait=False)


class TestBackgroundManagerLifecycle(BaseTestBackgroundManager):
    """Tests related to the lifecycle (start, stop, shutdown) of BackgroundManager."""

    @patch("threading.Timer")
    def test_start_background_cleanup(self, mock_timer):
        """Test that starting the cleanup schedules the first run."""
        self.manager.start_background_cleanup()
        mock_timer.assert_called_once_with(
            self.manager._cleanup_interval, self.manager._execute_cleanup
        )
        assert self.manager._cleanup_executor is not None

    @patch("threading.Timer")
    def test_start_background_cleanup_when_shutdown(self, mock_timer):
        """Test that cleanup does not start if manager is shut down."""
        self.manager._shutdown = True
        self.manager.start_background_cleanup()
        mock_timer.assert_not_called()
        assert self.manager._cleanup_executor is None

    @patch("threading.Timer")
    # pylint: disable=W0612
    def test_shutdown(self, mock_timer):
        """Test that shutdown stops the cleanup thread and executor."""
        # Start the manager
        self.manager.start_background_cleanup()
        mock_timer_instance = mock_timer.return_value
        mock_executor = self.manager._cleanup_executor
        mock_executor.shutdown = MagicMock()

        # Shutdown the manager
        self.manager.shutdown(wait=True)

        # Assertions
        assert self.manager._shutdown
        mock_timer_instance.cancel.assert_called_once()
        mock_executor.shutdown.assert_called_once_with(wait=True)

    def test_shutdown_already_shutdown(self):
        """Test shutdown when the manager is already shut down."""
        self.manager._shutdown = True
        with patch("smartpool.core.utils.safe_log") as mock_safe_log:
            self.manager.shutdown()
            mock_safe_log.assert_not_called()  # Should not log shutdown again

    def test_cleanup_does_not_run_if_disabled(self):
        """Test that background cleanup does not start if disabled in config."""
        self.mock_pool.default_config.enable_background_cleanup = False
        manager = BackgroundManager(self.mock_pool)

        with patch("threading.Timer") as mock_timer:
            manager.start_background_cleanup()
            mock_timer.assert_not_called()


class TestBackgroundManagerCleanupExecution(BaseTestBackgroundManager):
    """Tests related to the execution of cleanup tasks by BackgroundManager."""

    @patch.object(
        BackgroundManager, "_perform_cleanup_tasks", side_effect=RuntimeError("Test Exception")
    )
    @patch("threading.Timer")
    def test_execute_cleanup_with_exception(self, _mock_timer, _mock_perform_cleanup_tasks):
        """Test _execute_cleanup handles exceptions during cleanup tasks."""
        self.manager.start_background_cleanup()
        # Mock the executor's submit method to raise an exception immediately
        self.manager._cleanup_executor.submit = Mock(
            return_value=Mock(result=Mock(side_effect=RuntimeError("Test Exception")))
        )

        with (
            patch.object(self.manager, "_schedule_next_cleanup") as mock_schedule_next_cleanup,
            patch("smartpool.core.managers.background_manager.safe_log") as mock_safe_log,
        ):
            self.manager._execute_cleanup()
            self.manager._cleanup_executor.submit.assert_called_once()
            mock_safe_log.assert_called_once_with(self.manager.logger, logging.ERROR, ANY)
            mock_schedule_next_cleanup.assert_called_once()

    @patch("threading.Timer")
    def test_execute_cleanup_when_shutdown(self, mock_timer):
        """Test that _execute_cleanup does nothing if manager is shut down."""
        self.manager._shutdown = True
        self.manager._execute_cleanup()
        mock_timer.assert_not_called()

    @patch("threading.Timer")
    def test_execute_cleanup_no_executor(self, mock_timer):
        """Test _execute_cleanup when _cleanup_executor is None."""
        self.manager._cleanup_executor = None
        self.manager._execute_cleanup()
        mock_timer.assert_called_once()

    def test_perform_cleanup_tasks_no_sub_managers(self):
        """Test _perform_cleanup_tasks when sub-managers are not present."""
        del self.mock_pool.operations_manager
        del self.mock_pool.active_manager
        del self.mock_pool.stats

        self.manager._perform_cleanup_tasks()
        # No exceptions should be raised, and no calls to non-existent managers should occur.
        # The log for total_activity > 0 will not be called.

    def test_perform_cleanup_tasks_no_activity(self):
        """Test _perform_cleanup_tasks when no cleanup activity occurs."""
        self.mock_pool.operations_manager.cleanup_expired_objects.return_value = 0
        self.mock_pool.active_manager.cleanup_dead_weakrefs.return_value = 0
        self.mock_pool.operations_manager.cleanup_corruption_stats.return_value = 0

        with patch("smartpool.core.utils.safe_log") as mock_safe_log:
            self.manager._perform_cleanup_tasks()
            mock_safe_log.assert_not_called()

    def test_perform_cleanup_tasks_with_activity(self):
        """Test _perform_cleanup_tasks when cleanup activity occurs."""
        self.mock_pool.operations_manager.cleanup_expired_objects.return_value = 1
        self.mock_pool.active_manager.cleanup_dead_weakrefs.return_value = 0
        self.mock_pool.operations_manager.cleanup_corruption_stats.return_value = 0

        with patch("smartpool.core.managers.background_manager.safe_log") as mock_safe_log:
            self.manager._perform_cleanup_tasks()
            mock_safe_log.assert_called_once()
            assert mock_safe_log.call_args[0][0] == self.manager.logger
            assert mock_safe_log.call_args[0][1] == logging.INFO
            assert "Cleanup completed" in mock_safe_log.call_args[0][2]
            assert (
                "1 expired, 0 dead refs, 0 corruption stats cleaned"
                in mock_safe_log.call_args[0][2]
            )

    def test_perform_cleanup_tasks_exception_handling(self):
        """Test _perform_cleanup_tasks handles exceptions during its execution."""
        self.mock_pool.operations_manager.cleanup_expired_objects.side_effect = RuntimeError(
            "Cleanup Error"
        )

        with pytest.raises(BackgroundManagerError) as cm:
            self.manager._perform_cleanup_tasks()
        assert "Cleanup Error" in str(cm.value.cause)

    def test_perform_cleanup_tasks_delegation(self):
        """Test that the cleanup task calls the correct methods on other managers."""
        self.mock_pool.operations_manager.cleanup_expired_objects.return_value = 5
        self.mock_pool.active_manager.cleanup_dead_weakrefs.return_value = 2
        self.mock_pool.operations_manager.cleanup_corruption_stats.return_value = 1

        self.manager._perform_cleanup_tasks()

        # Verify that the correct cleanup methods were called
        self.mock_pool.operations_manager.cleanup_expired_objects.assert_called_once()
        self.mock_pool.active_manager.cleanup_dead_weakrefs.assert_called_once()
        self.mock_pool.operations_manager.cleanup_corruption_stats.assert_called_once()

        # Expired counter is now updated in PoolOperationsManager cleanup path.
        self.mock_pool.stats.increment.assert_not_called()


class TestBackgroundManagerScheduling(BaseTestBackgroundManager):
    """Tests related to the scheduling of cleanup tasks by BackgroundManager."""

    @patch("threading.Timer")
    def test_schedule_next_cleanup_when_shutdown(self, mock_timer):
        """Test that _schedule_next_cleanup does not schedule if manager is shut down."""
        self.manager._shutdown = True
        self.manager._schedule_next_cleanup()
        mock_timer.assert_not_called()
        assert self.manager._cleanup_thread is None

    @patch("threading.Timer")
    def test_restart_background_cleanup_active_thread(self, mock_timer):
        """Test restart_background_cleanup when a cleanup thread is active."""
        self.manager.start_background_cleanup()
        mock_timer_instance = mock_timer.return_value
        mock_timer_instance.is_alive.return_value = True

        with patch.object(self.manager, "_schedule_next_cleanup") as mock_schedule_next_cleanup:
            self.manager.restart_background_cleanup()
            mock_timer_instance.cancel.assert_called_once()
            mock_schedule_next_cleanup.assert_called_once()

    def test_restart_background_cleanup_when_shutdown(self):
        """Test restart_background_cleanup when the manager is shut down."""
        self.manager._shutdown = True
        with patch.object(self.manager, "_schedule_next_cleanup") as mock_schedule:
            self.manager.restart_background_cleanup()
            mock_schedule.assert_not_called()


class TestBackgroundManagerConfiguration(BaseTestBackgroundManager):
    """Tests related to configuration updates for BackgroundManager."""

    def test_update_cleanup_interval_seconds(self):
        """Test updating the cleanup interval dynamically."""
        with patch.object(self.manager, "restart_background_cleanup") as mock_restart:
            self.manager.update_cleanup_interval_seconds(120)
            assert self.manager._cleanup_interval == 120
            mock_restart.assert_called_once()

        with pytest.raises(PoolConfigurationError):
            self.manager.update_cleanup_interval_seconds(-10)

    def test_update_cleanup_interval_seconds_disabled_or_shutdown(self):
        """Test update_cleanup_interval when cleanup is disabled or manager is shut down."""
        # Test when cleanup is disabled
        disabled_pool = Mock()
        disabled_pool.default_config.enable_background_cleanup = False
        disabled_pool.default_config.cleanup_interval_seconds = 30
        disabled_pool.lock = MagicMock()
        disabled_pool.operations_manager = Mock()
        disabled_pool.active_manager = Mock()
        disabled_pool.stats = Mock()
        disabled_manager = BackgroundManager(disabled_pool)

        with patch.object(disabled_manager, "restart_background_cleanup") as mock_restart:
            disabled_manager.update_cleanup_interval_seconds(10)
            assert disabled_manager._cleanup_interval == 10
            mock_restart.assert_not_called()  # Should not restart if disabled

        # Test when manager is shut down
        shutdown_pool = Mock()
        shutdown_pool.default_config.enable_background_cleanup = True
        shutdown_pool.default_config.cleanup_interval_seconds = 30
        shutdown_pool.lock = MagicMock()
        shutdown_pool.operations_manager = Mock()
        shutdown_pool.active_manager = Mock()
        shutdown_pool.stats = Mock()
        shutdown_manager = BackgroundManager(shutdown_pool)
        shutdown_manager._shutdown = True

        with patch.object(shutdown_manager, "restart_background_cleanup") as mock_restart:
            shutdown_manager.update_cleanup_interval_seconds(20)
            assert shutdown_manager._cleanup_interval == 20
            mock_restart.assert_not_called()  # Should not restart if shut down

    def test_update_cleanup_interval_seconds_disabled_no_restart(self):
        """Test that restart_background_cleanup is not called when cleanup is disabled."""
        mock_pool = Mock()
        mock_pool.default_config.enable_background_cleanup = False
        mock_pool.default_config.cleanup_interval_seconds = 30
        mock_pool.lock = MagicMock()
        mock_pool.operations_manager = Mock()
        mock_pool.active_manager = Mock()
        mock_pool.stats = Mock()
        manager = BackgroundManager(mock_pool)

        with patch.object(manager, "restart_background_cleanup") as mock_restart:
            manager.update_cleanup_interval_seconds(10)
            mock_restart.assert_not_called()


class TestBackgroundManagerForceCleanup(BaseTestBackgroundManager):
    """Tests related to forcing immediate cleanup operations."""

    def test_force_cleanup_now_when_shutdown(self):
        """Test force_cleanup_now when the manager is shut down."""
        self.manager._shutdown = True
        result = self.manager.force_cleanup_now()
        assert result["error"] == "Manager is shut down"

    @patch("threading.Timer")
    def test_force_cleanup_now(self, mock_timer):
        """Test forcing an immediate cleanup."""
        # Start the manager to create a timer instance
        self.manager.start_background_cleanup()
        mock_timer_instance = mock_timer.return_value
        mock_timer_instance.is_alive.return_value = True

        with patch.object(self.manager.pool, "stats") as mock_stats:
            mock_stats.get.return_value = 5
            result = self.manager.force_cleanup_now()

            assert result["success"]
            assert result["duration_ms"] > 0
            assert result["objects_cleaned"] == 5
            # Check that cancel was called on the instance of the timer
            mock_timer_instance.cancel.assert_called_once()

    @patch("threading.Timer")
    def test_force_cleanup_now_exception(self, mock_timer):
        """Test force_cleanup_now handles exceptions during cleanup."""
        self.manager.start_background_cleanup()
        mock_timer_instance = mock_timer.return_value
        mock_timer_instance.is_alive.return_value = True

        with patch.object(
            self.manager, "_perform_cleanup_tasks", side_effect=RuntimeError("Force Cleanup Error")
        ):
            with patch("smartpool.core.managers.background_manager.safe_log") as mock_safe_log:
                result = self.manager.force_cleanup_now()
                assert not result["success"]
                assert "Force Cleanup Error" in result["error"]
                mock_safe_log.assert_called_once_with(self.manager.logger, logging.ERROR, ANY)


class TestBackgroundManagerStatus(BaseTestBackgroundManager):
    """Tests related to retrieving the status of the BackgroundManager."""

    def test_get_cleanup_status_no_thread_or_executor(self):
        """Test get_cleanup_status when no thread or executor is active."""
        self.manager._cleanup_thread = None
        self.manager._cleanup_executor = None
        status = self.manager.get_cleanup_status()
        assert not status["thread_active"]
        assert not status["executor_active"]
