"""
Background task management for the adaptive object memory pool.

This module provides the BackgroundManager class which handles periodic cleanup
operations and maintenance tasks for the memory pool system.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Dict, Optional

from smartpool.core.exceptions import BackgroundManagerError, PoolConfigurationError
from smartpool.core.utils import safe_log

if TYPE_CHECKING:  # pragma: no cover
    from smartpool.core.smartpool_manager import SmartObjectManager


class BackgroundManager:
    """
    Manages background tasks for the memory pool, primarily focusing on periodic cleanup
    operations to maintain pool health and efficiency.

    Responsibilities:
        - Orchestrating the periodic execution of cleanup tasks (e.g., removing expired objects,
          cleaning up dead weak references).
        - Managing the lifecycle of background threads and thread pools used for these tasks.
        - Ensuring proper shutdown of all background processes.
    """

    def __init__(self, pool: "SmartObjectManager"):
        """
        Initializes the BackgroundManager.

        Args:
            pool (SmartObjectManager): A reference to the main memory pool,
                                        used to access its configuration, logger,
                                        and other managers for cleanup tasks.
        """
        self.pool = pool
        self.logger = logging.getLogger(__name__)

        # Flag to indicate if the manager is shutting down.
        # Prevents new tasks from starting.
        self._shutdown = False

        # Thread pool executor for running cleanup tasks in the background.
        # Ensures tasks run asynchronously.
        self._cleanup_executor: Optional[ThreadPoolExecutor] = None
        # Timer thread for scheduling periodic cleanup operations.
        # Manages the interval between cleanups.
        self._cleanup_thread: Optional[threading.Timer] = None

        # Interval (in seconds) between cleanup operations,
        # retrieved from pool configuration.
        self._cleanup_interval = pool.default_config.cleanup_interval_seconds
        # Flag to enable or disable background cleanup,
        # retrieved from pool configuration.
        self._cleanup_enabled = pool.default_config.enable_background_cleanup

    def start_background_cleanup(self) -> None:
        """
        Initiates the background cleanup system. This method creates a ThreadPoolExecutor
        and schedules the first cleanup task if background cleanup is enabled and the manager
        is not already shut down.
        """
        if not self._cleanup_enabled or self._shutdown:
            return

        self._cleanup_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="pool-cleanup"
        )

        self._schedule_next_cleanup()
        safe_log(self.logger, logging.INFO, "Background cleanup started")

    def _schedule_next_cleanup(self) -> None:
        """
        Schedules the next execution of the cleanup task using a threading.Timer.
        This method is called recursively after each cleanup to ensure continuous periodic cleanup.
        It ensures that no new cleanup is scheduled if the manager is shutting down.
        """
        if self._shutdown:
            return

        self._cleanup_thread = threading.Timer(self._cleanup_interval, self._execute_cleanup)
        self._cleanup_thread.daemon = (
            True  # Allow the main program to exit even if this thread is running
        )
        self._cleanup_thread.start()

    def _execute_cleanup(self) -> None:
        """
        Executes a single cleanup session. This method submits the actual cleanup tasks
        to the internal ThreadPoolExecutor and waits for its completion with a timeout.
        It also handles logging of any errors during the cleanup process and reschedules
        the next cleanup.
        """
        if self._shutdown:
            return

        try:
            if self._cleanup_executor:
                # Submit the cleanup task with a timeout to prevent indefinite blocking.
                future = self._cleanup_executor.submit(self._perform_cleanup_tasks)
                future.result(timeout=30.0)  # Max 30 seconds for cleanup tasks
        except Exception as e:
            safe_log(self.logger, logging.ERROR, f"Background cleanup failed: {e}")
        finally:
            # Always reschedule the next cleanup, even if the current one failed.
            self._schedule_next_cleanup()

    def _perform_cleanup_tasks(self) -> Dict[str, int]:
        """
        Performs the actual cleanup operations by calling methods on other pool managers.
        This includes cleaning up expired objects, dead weak references,
        and old corruption statistics. It also records cleanup metrics and
        logs significant activity.

        Returns:
            Dict[str, int]: A dictionary containing cleanup statistics:
                - 'expired_objects': Number of expired objects removed
                - 'dead_weakrefs': Number of dead weak references cleaned
                - 'corruption_keys_cleaned': Number of corruption keys cleaned
                - 'duration_ms': Duration of cleanup in milliseconds

        Raises:
            Exception: Propagates any exceptions encountered during cleanup tasks.
        """
        current_time = time.time()

        # Acquire pool lock for operations that modify shared pool data structures.
        with self.pool.lock:
            cleanup_stats = {
                "expired_objects": 0,
                "dead_weakrefs": 0,
                "corruption_keys_cleaned": 0,
                "duration_ms": 0,
            }

            start_time = time.time()

            try:
                # 1. Clean up expired objects from the pool.
                if hasattr(self.pool, "operations_manager"):
                    expired = self.pool.operations_manager.cleanup_expired_objects(
                        self.pool.pool, current_time
                    )
                    cleanup_stats["expired_objects"] = expired

                # 2. Clean up dead WeakRefs from the active objects manager.
                if hasattr(self.pool, "active_manager"):
                    dead_refs = self.pool.active_manager.cleanup_dead_weakrefs()
                    cleanup_stats["dead_weakrefs"] = dead_refs

                # 3. Clean up old corruption statistics.
                if hasattr(self.pool, "operations_manager"):
                    corruption_cleaned = self.pool.operations_manager.cleanup_corruption_stats()
                    cleanup_stats["corruption_keys_cleaned"] = corruption_cleaned

                cleanup_stats["duration_ms"] = int((time.time() - start_time) * 1000)

                # Log cleanup activity if any significant changes occurred.
                total_activity = (
                    cleanup_stats["expired_objects"]
                    + cleanup_stats["dead_weakrefs"]
                    + cleanup_stats["corruption_keys_cleaned"]
                )

                if total_activity > 0:
                    safe_log(
                        self.logger,
                        logging.INFO,
                        f"Cleanup completed: {cleanup_stats['expired_objects']} expired, "
                        f"{cleanup_stats['dead_weakrefs']} dead refs, "
                        f"{cleanup_stats['corruption_keys_cleaned']} corruption stats cleaned "
                        f"in {cleanup_stats['duration_ms']:.1f}ms",
                    )

                return cleanup_stats

            except Exception as e:
                safe_log(self.logger, logging.ERROR, f"Error during cleanup tasks: {e}")
                raise BackgroundManagerError(task_name="cleanup_tasks", cause=e) from e

    def force_cleanup_now(self) -> Dict[str, Any]:
        """
        Forces an immediate execution of cleanup tasks, bypassing the scheduled interval.
        This method cancels any pending scheduled cleanup, performs the cleanup synchronously,
        and then reschedules the next periodic cleanup.

        Returns:
            dict: A dictionary containing the result of the forced cleanup, including
                'success', 'objects_cleaned', 'duration_ms', and 'timestamp'.
                If the manager is shut down, it returns an error message.
        """
        if self._shutdown:
            return {"error": "Manager is shut down"}

        try:
            # Cancel the next scheduled cleanup to avoid double execution.
            if self._cleanup_thread and self._cleanup_thread.is_alive():
                self._cleanup_thread.cancel()

            # Perform cleanup immediately in the current thread.
            start_time = time.perf_counter()
            cleanup_stats = self._perform_cleanup_tasks()
            duration = (time.perf_counter() - start_time) * 1000

            # Use the actual number of expired objects cleaned from the cleanup operation
            objects_cleaned = cleanup_stats["expired_objects"]

            # Reschedule the next periodic cleanup.
            self._schedule_next_cleanup()

            return {
                "success": True,
                "objects_cleaned": objects_cleaned,
                "duration_ms": duration,
                "timestamp": time.time(),
            }

        except (AttributeError, RuntimeError, ValueError, BackgroundManagerError) as e:
            safe_log(self.logger, logging.ERROR, f"Error during cleanup tasks: {e}")
            return {"success": False, "error": str(e), "timestamp": time.time()}

    def update_cleanup_interval_seconds(self, new_interval: float) -> None:
        """
        Updates the interval at which background cleanup tasks are executed.
        If the cleanup system is active, it will be restarted with the new interval.

        Args:
            new_interval (float): The new interval in seconds. Must be a positive value.

        Raises:
            PoolConfigurationError: If `new_interval` is not positive.
        """
        if new_interval <= 0:
            raise PoolConfigurationError(
                "Cleanup interval must be positive", context={"new_interval": new_interval}
            )

        old_interval = self._cleanup_interval
        self._cleanup_interval = new_interval

        # Restart the cleanup thread with the new timing if it's currently active.
        if self._cleanup_enabled and not self._shutdown:
            self.restart_background_cleanup()

        safe_log(
            self.logger,
            logging.INFO,
            f"Cleanup interval updated: {old_interval}s -> {new_interval}s",
        )

    def restart_background_cleanup(self) -> None:
        """
        Restarts the background cleanup system. This is useful after changing configuration
        parameters like the cleanup interval. It cancels any currently scheduled cleanup
        and schedules a new one immediately.
        """
        if self._shutdown:
            return

        # Stop the old cleanup thread if it's running.
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.cancel()

        # Schedule a new cleanup immediately.
        self._schedule_next_cleanup()
        safe_log(self.logger, logging.INFO, "Background cleanup restarted")

    def get_cleanup_status(self) -> dict:
        """
        Retrieves the current status of the background cleanup system.

        Returns:
            dict: A dictionary containing:
                  - 'enabled' (bool): Whether background cleanup is enabled.
                  - 'interval_seconds' (float): The configured cleanup interval.
                  - 'thread_active' (bool): Whether the cleanup timer thread is currently running.
                  - 'executor_active' (bool): Whether the cleanup thread pool executor is active.
                  - 'shutdown' (bool): Whether the manager is in a shutdown state.
        """
        return {
            "enabled": self._cleanup_enabled,
            "interval_seconds": self._cleanup_interval,
            "thread_active": (self._cleanup_thread is not None and self._cleanup_thread.is_alive()),
            "executor_active": (
                self._cleanup_executor is not None and not self._cleanup_executor._shutdown  # pylint: disable=protected-access
            ),  # Check if executor is not shut down
            "shutdown": self._shutdown,
        }

    def shutdown(self, wait: bool = True) -> None:
        """
        Shuts down the background manager cleanly. This involves stopping the cleanup timer
        thread and gracefully shutting down the thread pool executor.

        Args:
            wait (bool): If True, waits for all currently executing cleanup tasks to complete
                         before shutting down the executor. If False, tasks may be interrupted.
        """
        if self._shutdown:
            return

        self._shutdown = True

        # Stop the cleanup timer to prevent further scheduled tasks.
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.cancel()

        # Shut down the executor, optionally waiting for tasks to complete.
        if self._cleanup_executor:
            self._cleanup_executor.shutdown(wait=wait)

        safe_log(self.logger, logging.INFO, "Background manager shut down")
