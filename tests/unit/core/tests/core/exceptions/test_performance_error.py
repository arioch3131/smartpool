"""
Unit tests for performance-related exceptions.
"""

import unittest

from smartpool.core.exceptions import (
    ExcessiveObjectCreationError,
    HighLatencyError,
    LowHitRateError,
    PoolPerformanceError,
)


class TestPerformanceErrors(unittest.TestCase):
    """Test cases for performance exceptions."""

    def test_high_latency_error(self):
        """Test HighLatencyError for correct context."""
        error = HighLatencyError(
            operation="acquire", actual_latency_ms=150.5, threshold_ms=100.0, pool_key="test_pool"
        )
        self.assertEqual(error.context["operation"], "acquire")
        self.assertEqual(error.context["actual_latency_ms"], 150.5)
        self.assertEqual(error.context["threshold_ms"], 100.0)
        self.assertEqual(error.context["pool_key"], "test_pool")
        self.assertAlmostEqual(error.context["latency_ratio"], 1.505)
        self.assertIn("High latency for acquire: 150.50ms (threshold: 100.00ms)", str(error))

    def test_low_hit_rate_error(self):
        """Test LowHitRateError for correct context."""
        error = LowHitRateError(
            hit_rate=0.4, threshold=0.7, hits=40, misses=60, pool_key="test_pool"
        )
        self.assertEqual(error.context["hit_rate"], 0.4)
        self.assertEqual(error.context["threshold"], 0.7)
        self.assertEqual(error.context["hits"], 40)
        self.assertEqual(error.context["misses"], 60)
        self.assertEqual(error.context["total_requests"], 100)
        self.assertEqual(error.context["pool_key"], "test_pool")
        self.assertIn("Low hit rate: 40.0% (threshold: 70.0%) for 100 requests", str(error))

    def test_excessive_object_creation_error(self):
        """Test ExcessiveObjectCreationError for correct context."""
        error = ExcessiveObjectCreationError(
            creation_rate=15.0, threshold_rate=10.0, time_window_seconds=60, pool_key="test_pool"
        )
        self.assertEqual(error.context["creation_rate_per_second"], 15.0)
        self.assertEqual(error.context["threshold_rate_per_second"], 10.0)
        self.assertEqual(error.context["time_window_seconds"], 60)
        self.assertEqual(error.context["pool_key"], "test_pool")
        self.assertAlmostEqual(error.context["rate_ratio"], 1.5)
        self.assertIn("Excessive object creation: 15.0/s (threshold: 10.0/s)", str(error))

    def test_generic_pool_performance_error(self):
        """Test the generic PoolPerformanceError."""
        error = PoolPerformanceError("Generic performance error")
        self.assertEqual(error.message, "Generic performance error")


if __name__ == "__main__":
    unittest.main()
