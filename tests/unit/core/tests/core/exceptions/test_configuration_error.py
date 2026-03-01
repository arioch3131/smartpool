"""
Unit tests for configuration-related exceptions.
"""

import unittest

from smartpool.core.exceptions.configuration_error import (
    ConfigurationConflictError,
    InvalidPoolSizeError,
    InvalidPresetError,
    InvalidTTLError,
    PoolConfigurationError,
)


class TestConfigurationErrors(unittest.TestCase):
    """Test cases for configuration exceptions."""

    def test_invalid_pool_size_error(self):
        """Test InvalidPoolSizeError for correct context."""
        error = InvalidPoolSizeError(provided_size=-5, min_size=1, max_objects_per_key=100)
        self.assertEqual(error.context["provided_size"], -5)
        self.assertEqual(error.context["min_size"], 1)
        self.assertEqual(error.context["max_objects_per_key"], 100)
        self.assertIn("Pool size -5 invalid", str(error))

    def test_invalid_ttl_error(self):
        """Test InvalidTTLError for correct context."""
        error = InvalidTTLError(provided_ttl=-10)
        self.assertEqual(error.context["provided_ttl"], -10)
        self.assertIn("TTL '-10' invalid", str(error))

    def test_invalid_preset_error(self):
        """Test InvalidPresetError for correct context."""
        available = ["preset1", "preset2"]
        error = InvalidPresetError(provided_preset="unknown", available_presets=available)
        self.assertEqual(error.context["provided_preset"], "unknown")
        self.assertEqual(error.context["available_presets"], available)
        self.assertIn("Preset 'unknown' invalid", str(error))

    def test_configuration_conflict_error(self):
        """Test ConfigurationConflictError for correct context."""
        conflicts = {"param1": True, "param2": False}
        reason = "param1 and param2 cannot be used together"
        error = ConfigurationConflictError(conflicting_params=conflicts, reason=reason)
        self.assertEqual(error.context["conflicting_params"], conflicts)
        self.assertEqual(error.context["reason"], reason)
        self.assertIn("Configuration conflict", str(error))

    def test_generic_pool_configuration_error(self):
        """Test the generic PoolConfigurationError."""
        error = PoolConfigurationError("Generic config error", context={"detail": "some detail"})
        self.assertEqual(error.message, "Generic config error")
        self.assertEqual(error.context["detail"], "some detail")


if __name__ == "__main__":
    unittest.main()
