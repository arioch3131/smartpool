"""
Unit tests for factory-related exceptions.
"""

import unittest

from smartpool.core.exceptions import (
    FactoryCreationError,
    FactoryDestroyError,
    FactoryError,
    FactoryKeyGenerationError,
    FactoryResetError,
    FactoryValidationError,
)


class TestFactoryErrors(unittest.TestCase):
    """Test cases for factory exceptions."""

    def test_factory_creation_error(self):
        """Test FactoryCreationError for correct context."""
        cause = ValueError("Underlying issue")
        error = FactoryCreationError(
            factory_class="MyFactory", args=(1, 2), kwargs_dict={"c": 3}, cause=cause
        )
        self.assertEqual(error.context["factory_class"], "MyFactory")
        self.assertEqual(error.context["method_name"], "create")
        self.assertEqual(error.context["args"], (1, 2))
        self.assertEqual(error.context["kwargs"], {"c": 3})
        self.assertEqual(error.cause, cause)

    def test_factory_validation_error(self):
        """Test FactoryValidationError for correct context."""
        error = FactoryValidationError(
            factory_class="MyFactory", validation_attempts=3, max_attempts=3
        )
        self.assertEqual(error.context["validation_attempts"], 3)
        self.assertEqual(error.context["max_attempts"], 3)
        self.assertTrue(error.context["attempts_exhausted"])
        self.assertIn("Validation failed after 3/3 attempts", str(error))

    def test_factory_reset_error(self):
        """Test FactoryResetError for correct context."""
        error = FactoryResetError(factory_class="MyFactory", object_type="MyObject")
        self.assertEqual(error.context["factory_class"], "MyFactory")
        self.assertEqual(error.context["method_name"], "reset")
        self.assertEqual(error.context["object_type"], "MyObject")

    def test_factory_destroy_error(self):
        """Test FactoryDestroyError for correct context."""
        error = FactoryDestroyError(factory_class="MyFactory", object_type="MyObject")
        self.assertEqual(error.context["factory_class"], "MyFactory")
        self.assertEqual(error.context["method_name"], "destroy")
        self.assertEqual(error.context["object_type"], "MyObject")

    def test_factory_key_generation_error(self):
        """Test FactoryKeyGenerationError for correct context."""
        error = FactoryKeyGenerationError(factory_class="MyFactory")
        self.assertEqual(error.context["factory_class"], "MyFactory")
        self.assertEqual(error.context["method_name"], "get_key")

    def test_generic_factory_error(self):
        """Test the generic FactoryError."""
        error = FactoryError("Generic factory error", factory_class="BaseFactory")
        self.assertEqual(error.message, "Generic factory error")
        self.assertEqual(error.context["factory_class"], "BaseFactory")


if __name__ == "__main__":
    unittest.main()
