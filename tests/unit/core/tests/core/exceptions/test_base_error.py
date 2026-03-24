"""
Unit tests for the SmartPoolError base exception.
"""

import time
import unittest

from smartpool.core.exceptions import SmartPoolError


class TestSmartPoolError(unittest.TestCase):
    """Test cases for the base SmartPoolError exception."""

    def test_basic_exception(self):
        """Test basic exception attributes."""
        error = SmartPoolError("A test error")
        self.assertEqual(error.message, "A test error")
        self.assertEqual(error.error_code, "SmartPoolError")
        self.assertIsNone(error.cause)
        self.assertAlmostEqual(error.timestamp, time.time(), delta=1)

    def test_exception_with_context(self):
        """Test exception with additional context."""
        context = {"key": "value", "num": 123}
        error = SmartPoolError("Context error", context=context)
        self.assertEqual(error.context, context)
        self.assertIn("key=value", str(error))
        self.assertIn("num=123", str(error))

    def test_exception_with_cause(self):
        """Test exception with a causing exception."""
        cause = ValueError("Original cause")
        error = SmartPoolError("Chained error", cause=cause)
        self.assertEqual(error.cause, cause)
        self.assertIn("caused by: Original cause", str(error))

    def test_to_dict_serialization(self):
        """Test the to_dict serialization method."""
        cause = ValueError("Root cause")
        context = {"id": 42}
        error = SmartPoolError(
            message="Serialization test", error_code="TEST001", context=context, cause=cause
        )

        error_dict = error.to_dict()

        self.assertEqual(error_dict["error_type"], "SmartPoolError")
        self.assertEqual(error_dict["error_code"], "TEST001")
        self.assertEqual(error_dict["message"], "Serialization test")
        self.assertEqual(error_dict["context"], context)
        self.assertEqual(error_dict["cause"], "Root cause")
        self.assertAlmostEqual(error_dict["timestamp"], error.timestamp, delta=0.1)


if __name__ == "__main__":
    unittest.main()
