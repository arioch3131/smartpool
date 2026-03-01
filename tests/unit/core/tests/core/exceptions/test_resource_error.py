"""
Unit tests for resource-related exceptions.
"""

import unittest

from smartpool.core.exceptions import (
    DiskSpaceExhaustedError,
    MemoryLimitExceededError,
    PoolResourceError,
    ResourceLeakDetectedError,
    ThreadPoolExhaustedError,
)


class TestResourceErrors(unittest.TestCase):
    """Test cases for resource exceptions."""

    def test_memory_limit_exceeded_error(self):
        """Test MemoryLimitExceededError for correct context."""
        error = MemoryLimitExceededError(
            current_usage=150000000, limit=100000000, component="cache"
        )
        self.assertEqual(error.context["current_usage_bytes"], 150000000)
        self.assertEqual(error.context["limit_bytes"], 100000000)
        self.assertAlmostEqual(error.context["current_usage_mb"], 143.05)
        self.assertAlmostEqual(error.context["limit_mb"], 95.37)
        self.assertAlmostEqual(error.context["usage_percent"], 150.0)
        self.assertEqual(error.context["component"], "cache")
        self.assertIn("Memory limit exceeded for cache: 143.1MB/95.4MB", str(error))

    def test_thread_pool_exhausted_error(self):
        """Test ThreadPoolExhaustedError for correct context."""
        error = ThreadPoolExhaustedError(active_threads=10, max_threads=10, waiting_tasks=5)
        self.assertEqual(error.context["active_threads"], 10)
        self.assertEqual(error.context["max_threads"], 10)
        self.assertEqual(error.context["waiting_tasks"], 5)
        self.assertEqual(error.context["utilization_percent"], 100.0)
        self.assertIn("Thread pool exhausted: 10/10 active threads, 5 waiting tasks", str(error))

    def test_resource_leak_detected_error(self):
        """Test ResourceLeakDetectedError for correct context."""
        error = ResourceLeakDetectedError(
            resource_type="file_handle",
            leaked_count=10,
            expected_count=0,
            detection_method="manual",
        )
        self.assertEqual(error.context["resource_type"], "file_handle")
        self.assertEqual(error.context["leaked_count"], 10)
        self.assertEqual(error.context["expected_count"], 0)
        self.assertEqual(error.context["detection_method"], "manual")
        self.assertEqual(error.context["leak_ratio"], 10.0)
        self.assertIn(
            "Resource leak detected for file_handle: 10 unreleased resources (expected: 0)",
            str(error),
        )

    def test_disk_space_exhausted_error(self):
        """Test DiskSpaceExhaustedError for correct context."""
        error = DiskSpaceExhaustedError(
            available_bytes=100000000, required_bytes=500000000, path="/data"
        )
        self.assertEqual(error.context["available_bytes"], 100000000)
        self.assertEqual(error.context["required_bytes"], 500000000)
        self.assertAlmostEqual(error.context["available_mb"], 95.37)
        self.assertAlmostEqual(error.context["required_mb"], 476.84)
        self.assertEqual(error.context["path"], "/data")
        self.assertIn(
            "Insufficient disk space on /data: 95.4MB available, 476.8MB required", str(error)
        )

    def test_generic_pool_resource_error(self):
        """Test the generic PoolResourceError."""
        error = PoolResourceError("Generic resource error")
        self.assertEqual(error.message, "Generic resource error")


if __name__ == "__main__":
    unittest.main()
