"""
Unit tests for lifecycle-related exceptions.
"""

import time
import unittest

from smartpool.core.exceptions import (
    BackgroundManagerError,
    ManagerSynchronizationError,
    PoolAlreadyShutdownError,
    PoolInitializationError,
    PoolLifecycleError,
)


class TestLifecycleErrors(unittest.TestCase):
    """Test cases for lifecycle exceptions."""

    def test_pool_already_shutdown_error(self):
        """Test PoolAlreadyShutdownError for correct context."""
        shutdown_time = time.time() - 10  # 10 seconds ago
        error = PoolAlreadyShutdownError(operation="acquire", shutdown_time=shutdown_time)
        self.assertEqual(error.context["attempted_operation"], "acquire")
        self.assertEqual(error.context["shutdown_time"], shutdown_time)
        self.assertAlmostEqual(error.context["time_since_shutdown"], 10, delta=1)
        self.assertIn("Cannot execute 'acquire': pool is shutdown", str(error))

    def test_pool_initialization_error(self):
        """Test PoolInitializationError for correct context."""
        cause = RuntimeError("DB connection failed")
        error = PoolInitializationError(component="database", stage="connect", cause=cause)
        self.assertEqual(error.context["failed_component"], "database")
        self.assertEqual(error.context["initialization_stage"], "connect")
        self.assertEqual(error.cause, cause)
        self.assertIn(
            "Initialization failed for component 'database' during stage 'connect'", str(error)
        )

    def test_background_manager_error(self):
        """Test BackgroundManagerError for correct context."""
        cause = Exception("Task failed")
        error = BackgroundManagerError(
            task_name="cleanup_task", error_type="execution", cause=cause
        )
        self.assertEqual(error.context["task_name"], "cleanup_task")
        self.assertEqual(error.context["error_type"], "execution")
        self.assertEqual(error.cause, cause)
        self.assertIn("Error execution in background task 'cleanup_task'", str(error))

    def test_manager_synchronization_error(self):
        """Test ManagerSynchronizationError for correct context."""
        error = ManagerSynchronizationError(
            manager1="PoolManager", manager2="ActiveManager", operation="transfer"
        )
        self.assertEqual(error.context["manager1"], "PoolManager")
        self.assertEqual(error.context["manager2"], "ActiveManager")
        self.assertEqual(error.context["operation"], "transfer")
        self.assertIn(
            "Synchronization error between PoolManager and ActiveManager during 'transfer'",
            str(error),
        )

    def test_generic_pool_lifecycle_error(self):
        """Test the generic PoolLifecycleError."""
        error = PoolLifecycleError("Generic lifecycle error")
        self.assertEqual(error.message, "Generic lifecycle error")


if __name__ == "__main__":
    unittest.main()
