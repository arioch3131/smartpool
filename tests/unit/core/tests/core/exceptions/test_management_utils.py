"""
Unit tests for exception management utilities.
"""

import time
import unittest

from smartpool.core.exceptions import (
    ExceptionMetrics,
    ExceptionPolicy,
    FactoryValidationError,
    ObjectCorruptionError,
    SmartPoolError,
)


class TestExceptionPolicy(unittest.TestCase):
    """Test cases for ExceptionPolicy."""

    def setUp(self):
        self.policy = ExceptionPolicy()

    def test_default_should_raise(self):
        """Test default should_raise behavior (not strict mode)."""
        self.assertFalse(self.policy.should_raise(FactoryValidationError))
        self.assertFalse(self.policy.should_raise(ObjectCorruptionError))
        self.assertTrue(self.policy.should_raise(SmartPoolError))  # Generic error

    def test_strict_mode_should_raise(self):
        """Test strict mode should_raise behavior."""
        self.policy.strict_mode = True
        self.assertTrue(self.policy.should_raise(FactoryValidationError))
        self.assertTrue(self.policy.should_raise(SmartPoolError))

    def test_should_log(self):
        """Test should_log behavior."""
        self.assertTrue(self.policy.should_log())
        self.policy.log_all_exceptions = False
        self.assertFalse(self.policy.should_log())

    def test_truncate_context(self):
        """Test context truncation."""
        long_context = {"data": "a" * 2000}
        truncated = self.policy.truncate_context(long_context)
        self.assertIn("_truncated", truncated)
        self.assertIn("_original_size", truncated)
        self.assertLess(len(str(truncated)), len(str(long_context)))

        short_context = {"data": "a" * 10}
        not_truncated = self.policy.truncate_context(short_context)
        self.assertNotIn("_truncated", not_truncated)


class TestExceptionMetrics(unittest.TestCase):
    """Test cases for ExceptionMetrics."""

    def setUp(self):
        self.metrics = ExceptionMetrics()

    def test_record_exception(self):
        """Test recording of exceptions."""
        error1 = SmartPoolError("Error A", error_code="CODE_A", context={"pool_key": "pool1"})
        error2 = SmartPoolError("Error B", error_code="CODE_B", context={"pool_key": "pool2"})
        error3 = SmartPoolError("Error A", error_code="CODE_A", context={"pool_key": "pool1"})

        self.metrics.record_exception(error1)
        self.metrics.record_exception(error2)
        self.metrics.record_exception(error3)

        self.assertEqual(self.metrics.exception_counters["CODE_A"], 2)
        self.assertEqual(self.metrics.exception_counters["CODE_B"], 1)
        self.assertEqual(len(self.metrics.exception_patterns[("CODE_A", "pool1")]), 2)
        self.assertEqual(len(self.metrics.exception_patterns[("CODE_B", "pool2")]), 1)

    def test_get_error_rate(self):
        """Test error rate calculation."""
        error = SmartPoolError("Test", error_code="TEST_CODE", context={"pool_key": "pool_rate"})
        # Record one exception at time 0
        with unittest.mock.patch("time.time", return_value=0):
            self.metrics.record_exception(error)

        # Record another exception at time 100
        with unittest.mock.patch("time.time", return_value=100):
            self.metrics.record_exception(error)

        # Calculate rate for a window of 300 seconds, ending at time 300
        with unittest.mock.patch("time.time", return_value=300):
            rate = self.metrics.get_error_rate("TEST_CODE", window_seconds=300)
            # Two exceptions in a 300 second window, so rate should be 2/300
            self.assertAlmostEqual(rate, 2 / 300)
            self.assertGreater(rate, 0)

    def test_get_top_errors(self):
        """Test getting top errors."""
        self.metrics.record_exception(SmartPoolError("E1", error_code="E1"))
        self.metrics.record_exception(SmartPoolError("E2", error_code="E2"))
        self.metrics.record_exception(SmartPoolError("E1", error_code="E1"))

        top_errors = self.metrics.get_top_errors(1)
        self.assertEqual(top_errors, [("E1", 2)])

    def test_detect_error_spikes(self):
        """Test error spike detection."""
        # Simulate a baseline error: 5 errors over 300 seconds (baseline window)
        # Rate = 5 / 300 = 0.0166
        for i in range(5):
            with unittest.mock.patch("time.time", return_value=i * 60):  # 0, 60, 120, 180, 240
                self.metrics.record_exception(SmartPoolError("SpikeTest", error_code="SPIKE"))

        # Simulate a spike: 20 errors over the next 5 minutes (recent window)
        # Starting at time 300, ending at 600
        # Rate = 20 / 300 = 0.0666
        # Threshold = baseline_rate * 3 = 0.0166 * 3 = 0.05
        # So, 0.0666 > 0.05, should detect spike
        for i in range(20):
            with unittest.mock.patch("time.time", return_value=300 + i * (300 / 20)):
                self.metrics.record_exception(SmartPoolError("SpikeTest", error_code="SPIKE"))

        # Check for spikes at time 600
        with unittest.mock.patch("time.time", return_value=600):
            spikes = self.metrics.detect_error_spikes()
            self.assertIn("SPIKE", spikes)

    def test_cleanup_old_data(self):
        """Test cleanup of old data."""
        error = SmartPoolError("OldData", error_code="OLD", context={"pool_key": "old_pool"})
        self.metrics.record_exception(error)

        # Simulate time passing beyond retention
        with unittest.mock.patch("time.time", return_value=time.time() + (25 * 3600)):
            self.metrics._cleanup_old_data()  # pylint: disable=protected-access
            self.assertNotIn(("OLD", "old_pool"), self.metrics.exception_patterns)

    def test_non_matching_error_code_and_no_spike_path(self):
        """Test non-matching code in get_error_rate and no-spike path in detection."""
        with unittest.mock.patch("time.time", return_value=100):
            self.metrics.record_exception(
                SmartPoolError("Stable", error_code="STABLE", context={"pool_key": "pool1"})
            )

        with unittest.mock.patch("time.time", return_value=200):
            self.metrics.record_exception(
                SmartPoolError("Other", error_code="OTHER", context={"pool_key": "pool1"})
            )

        with unittest.mock.patch("time.time", return_value=300):
            stable_rate = self.metrics.get_error_rate("STABLE", window_seconds=500)
            self.assertGreater(stable_rate, 0)
            self.assertLess(stable_rate, 1)

            spikes = self.metrics.detect_error_spikes(threshold_multiplier=20.0)
            self.assertNotIn("STABLE", spikes)
            self.assertNotIn("OTHER", spikes)


if __name__ == "__main__":
    unittest.main()
