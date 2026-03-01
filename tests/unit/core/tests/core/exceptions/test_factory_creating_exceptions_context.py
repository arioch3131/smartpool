"""
Unit tests for the SmartPoolExceptionFactory.
"""

import unittest

from smartpool.core.exceptions import (
    AcquisitionTimeoutError,
    FactoryCreationError,
    FactoryDestroyError,
    FactoryError,
    FactoryKeyGenerationError,
    FactoryResetError,
    FactoryValidationError,
    ObjectCorruptionError,
    ObjectCreationFailedError,
    ObjectResetFailedError,
    ObjectValidationFailedError,
    PoolExhaustedError,
    PoolOperationError,
    SmartPoolExceptionFactory,
)


class TestSmartPoolExceptionFactory(unittest.TestCase):
    """Test cases for SmartPoolExceptionFactory."""

    def test_create_factory_creation_error(self):
        """Test creation of FactoryCreationError."""
        cause = TypeError("Missing arg")
        exc = SmartPoolExceptionFactory.create_factory_error(
            error_type="creation",
            factory_class="TestFactory",
            method_name="create",
            cause=cause,
            args=(1,),
            kwargs={"param": "value"},
        )
        self.assertIsInstance(exc, FactoryCreationError)
        self.assertEqual(exc.context["factory_class"], "TestFactory")
        self.assertEqual(exc.context["method_name"], "create")
        self.assertEqual(exc.context["args"], (1,))
        self.assertEqual(exc.context["kwargs"], {"param": "value"})
        self.assertEqual(exc.cause, cause)

    def test_create_factory_validation_error(self):
        """Test creation of FactoryValidationError."""
        exc = SmartPoolExceptionFactory.create_factory_error(
            error_type="validation",
            factory_class="TestFactory",
            method_name="validate",
            attempts=2,
            max_attempts=3,
        )
        self.assertIsInstance(exc, FactoryValidationError)
        self.assertEqual(exc.context["validation_attempts"], 2)
        self.assertEqual(exc.context["max_attempts"], 3)

    def test_create_factory_reset_error(self):
        """Test creation of FactoryResetError."""
        exc = SmartPoolExceptionFactory.create_factory_error(
            error_type="reset",
            factory_class="TestFactory",
            method_name="reset",
            object_type="MyObject",
        )
        self.assertIsInstance(exc, FactoryResetError)
        self.assertEqual(exc.context["object_type"], "MyObject")

    def test_create_factory_destroy_error(self):
        """Test creation of FactoryDestroyError."""
        exc = SmartPoolExceptionFactory.create_factory_error(
            error_type="destroy",
            factory_class="TestFactory",
            method_name="destroy",
            object_type="MyObject",
        )
        self.assertIsInstance(exc, FactoryDestroyError)
        self.assertEqual(exc.context["object_type"], "MyObject")

    def test_create_factory_key_generation_error(self):
        """Test creation of FactoryKeyGenerationError."""
        exc = SmartPoolExceptionFactory.create_factory_error(
            error_type="key_generation",
            factory_class="TestFactory",
            method_name="get_key",
            args=(1,),
            kwargs={"param": "value"},
        )
        self.assertIsInstance(exc, FactoryKeyGenerationError)
        self.assertEqual(exc.context["factory_class"], "TestFactory")
        self.assertEqual(exc.context["method_name"], "get_key")
        self.assertEqual(exc.context["args"], (1,))
        self.assertEqual(exc.context["kwargs"], {"param": "value"})

    def test_create_generic_factory_error(self):
        """Test creation of generic FactoryError."""
        exc = SmartPoolExceptionFactory.create_factory_error(
            error_type="unknown",
            factory_class="TestFactory",
            method_name="some_method",
            message="Custom generic error",
            extra_context="extra",
        )
        self.assertIsInstance(exc, FactoryError)
        self.assertEqual(exc.message, "Custom generic error")
        self.assertEqual(exc.context["factory_class"], "TestFactory")
        self.assertEqual(exc.context["method_name"], "some_method")
        self.assertEqual(exc.context["extra_context"], "extra")

    def test_create_pool_exhausted_error(self):
        """Test creation of PoolExhaustedError."""
        exc = SmartPoolExceptionFactory.create_pool_operation_error(
            error_type="exhausted",
            pool_key="my_pool",
            current_size=5,
            max_objects_per_key=5,
            active_objects_count=3,
        )
        self.assertIsInstance(exc, PoolExhaustedError)
        self.assertEqual(exc.context["pool_key"], "my_pool")
        self.assertEqual(exc.context["current_size"], 5)

    def test_create_acquisition_timeout_error(self):
        """Test creation of AcquisitionTimeoutError."""
        exc = SmartPoolExceptionFactory.create_pool_operation_error(
            error_type="timeout", pool_key="my_pool", timeout_seconds=10, retry_attempts=2
        )
        self.assertIsInstance(exc, AcquisitionTimeoutError)
        self.assertEqual(exc.context["timeout_seconds"], 10)

    def test_create_object_creation_failed_error(self):
        """Test creation of ObjectCreationFailedError."""
        cause = ConnectionError("No connection")
        exc = SmartPoolExceptionFactory.create_pool_operation_error(
            error_type="creation_failed", pool_key="my_pool", cause=cause, attempts=1
        )
        self.assertIsInstance(exc, ObjectCreationFailedError)
        self.assertEqual(exc.context["pool_key"], "my_pool")
        self.assertEqual(exc.context["creation_attempts"], 1)
        self.assertEqual(exc.cause, cause)

    def test_create_object_reset_failed_error(self):
        """Test creation of ObjectResetFailedError."""
        cause = RuntimeError("Reset failure")
        exc = SmartPoolExceptionFactory.create_pool_operation_error(
            error_type="reset", pool_key="my_pool", cause=cause
        )
        self.assertIsInstance(exc, ObjectResetFailedError)
        self.assertEqual(exc.context["pool_key"], "my_pool")
        self.assertEqual(exc.cause, cause)

    def test_create_object_validation_failed_error(self):
        """Test creation of ObjectValidationFailedError."""
        exc = SmartPoolExceptionFactory.create_pool_operation_error(
            error_type="validation",
            pool_key="my_pool",
            reason="invalid schema",
            attempts=3,
        )
        self.assertIsInstance(exc, ObjectValidationFailedError)
        self.assertEqual(exc.context["pool_key"], "my_pool")
        self.assertEqual(exc.context["validation_reason"], "invalid schema")
        self.assertEqual(exc.context["validation_attempts"], 3)

    def test_create_object_corruption_error(self):
        """Test creation of ObjectCorruptionError."""
        exc = SmartPoolExceptionFactory.create_pool_operation_error(
            error_type="corruption",
            pool_key="my_pool",
            corruption_count=2,
            threshold=5,
            corruption_type="data_integrity",
        )
        self.assertIsInstance(exc, ObjectCorruptionError)
        self.assertEqual(exc.context["corruption_count"], 2)

    def test_create_generic_pool_operation_error(self):
        """Test creation of generic PoolOperationError."""
        exc = SmartPoolExceptionFactory.create_pool_operation_error(
            error_type="unknown_operation", pool_key="my_pool"
        )
        self.assertIsInstance(exc, PoolOperationError)
        self.assertIn("Operation error unknown_operation for pool 'my_pool'", str(exc))


if __name__ == "__main__":
    unittest.main()
