"""
Unit tests for pool operation-related exceptions.
"""

import unittest

from smartpool.core.exceptions import (
    AcquisitionTimeoutError,
    CorruptionThresholdExceededError,
    ObjectCorruptionError,
    ObjectCreationFailedError,
    ObjectResetFailedError,
    ObjectStateCorruptedError,
    ObjectValidationFailedError,
    PoolExhaustedError,
    PoolOperationError,
)


class TestOperationErrors(unittest.TestCase):
    """Test cases for pool operation exceptions."""

    def test_pool_exhausted_error(self):
        """Test PoolExhaustedError for correct context."""
        error = PoolExhaustedError(
            pool_key="test_pool", current_size=10, max_objects_per_key=10, active_objects_count=5
        )
        self.assertEqual(error.context["pool_key"], "test_pool")
        self.assertEqual(error.context["current_size"], 10)
        self.assertEqual(error.context["max_objects_per_key"], 10)
        self.assertEqual(error.context["active_objects_count"], 5)
        self.assertEqual(error.context["utilization_percent"], 100.0)
        self.assertIn(
            "Pool exhausted for key 'test_pool' (10/10 objects, 100.0% utilization)", str(error)
        )

    def test_acquisition_timeout_error(self):
        """Test AcquisitionTimeoutError for correct context."""
        error = AcquisitionTimeoutError(
            timeout_seconds=5.0, pool_key="timeout_pool", retry_attempts=3
        )
        self.assertEqual(error.context["timeout_seconds"], 5.0)
        self.assertEqual(error.context["pool_key"], "timeout_pool")
        self.assertEqual(error.context["retry_attempts"], 3)
        self.assertIn("Acquisition timeout after 5.0s for key 'timeout_pool'", str(error))

    def test_object_creation_failed_error(self):
        """Test ObjectCreationFailedError for correct context."""
        cause = ConnectionRefusedError("Cannot connect")
        error = ObjectCreationFailedError(pool_key="create_pool", attempts=2, cause=cause)
        self.assertEqual(error.context["pool_key"], "create_pool")
        self.assertEqual(error.context["creation_attempts"], 2)
        self.assertEqual(error.cause, cause)
        self.assertIn("Object creation failed for key 'create_pool' after 2 attempt(s)", str(error))

    def test_object_validation_failed_error(self):
        """Test ObjectValidationFailedError for correct context."""
        error = ObjectValidationFailedError(
            pool_key="validate_pool", reason="corrupted data", attempts=1
        )
        self.assertEqual(error.context["pool_key"], "validate_pool")
        self.assertEqual(error.context["validation_reason"], "corrupted data")
        self.assertEqual(error.context["validation_attempts"], 1)
        self.assertIn(
            "Validation failed during release for 'validate_pool': corrupted data", str(error)
        )

    def test_object_reset_failed_error(self):
        """Test ObjectResetFailedError for correct context."""
        cause = RuntimeError("Reset method failed")
        error = ObjectResetFailedError(pool_key="reset_pool", cause=cause)
        self.assertEqual(error.context["pool_key"], "reset_pool")
        self.assertEqual(error.cause, cause)
        self.assertIn("Reset failed during release for 'reset_pool'", str(error))

    def test_object_corruption_error(self):
        """Test ObjectCorruptionError for correct context."""
        error = ObjectCorruptionError(
            pool_key="corrupt_pool",
            corruption_count=3,
            threshold=5,
            corruption_type="data_mismatch",
        )
        self.assertEqual(error.context["pool_key"], "corrupt_pool")
        self.assertEqual(error.context["corruption_count"], 3)
        self.assertEqual(error.context["threshold"], 5)
        self.assertEqual(error.context["corruption_type"], "data_mismatch")
        self.assertFalse(error.context["threshold_exceeded"])
        self.assertIn("Corruption data_mismatch detected for 'corrupt_pool' (3/5)", str(error))

    def test_corruption_threshold_exceeded_error(self):
        """Test CorruptionThresholdExceededError for correct context."""
        error = CorruptionThresholdExceededError(
            pool_key="threshold_pool", corruption_count=5, threshold=5
        )
        self.assertEqual(error.context["corruption_count"], 5)
        self.assertEqual(error.context["threshold"], 5)
        self.assertTrue(error.context["threshold_exceeded"])
        self.assertIn("Corruption threshold exceeded for 'threshold_pool' (5/5)", str(error))

    def test_object_state_corrupted_error(self):
        """Test ObjectStateCorruptedError for correct context."""
        error = ObjectStateCorruptedError(
            pool_key="state_pool", object_id="obj123", state_info={"status": "invalid"}
        )
        self.assertEqual(error.context["pool_key"], "state_pool")
        self.assertEqual(error.context["object_id"], "obj123")
        self.assertEqual(error.context["state_info"]["status"], "invalid")
        self.assertIn(
            "Corrupted state detected for object 'obj123' in pool 'state_pool'", str(error)
        )

    def test_generic_pool_operation_error(self):
        """Test the generic PoolOperationError."""
        error = PoolOperationError("Generic operation error")
        self.assertEqual(error.message, "Generic operation error")


if __name__ == "__main__":
    unittest.main()
