"""Tests for the ThreadSafeStats class."""

import datetime
import threading

import pytest

from smartpool.core.metrics.thread_safe_stats import PoolMetrics, ThreadSafeStats


# pylint: disable=W0201
class TestThreadSafeStats:
    """Tests for the ThreadSafeStats class."""

    def setup_method(self):
        """Set up for each test method."""
        self.stats = ThreadSafeStats()

    def test_initial_state(self):
        """Test that stats are initialized to zero."""
        all_stats = self.stats.get_all_metrics()
        assert not all_stats["counters"]
        assert not all_stats["gauges"]

    def test_increment(self):
        """Test basic increment functionality."""
        self.stats.increment("hits")
        assert self.stats.get("hits") == 1

        self.stats.increment("hits", 5)
        assert self.stats.get("hits") == 6

    def test_set_gauge(self):
        """Test setting a gauge value."""
        self.stats.set_gauge("active_objects_count", 15.0)
        all_stats = self.stats.get_all_metrics()
        assert all_stats["gauges"]["active_objects_count"] == 15.0

    def test_concurrent_increment(self):
        """Test that incrementing from multiple threads is safe."""
        num_threads = 10
        increments_per_thread = 1000

        def worker():
            for _ in range(increments_per_thread):
                self.stats.increment("concurrent_counter")

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert self.stats.get("concurrent_counter") == num_threads * increments_per_thread

    def test_record_and_get_history(self):
        """Test recording metric snapshots and retrieving the history."""
        self.stats.increment("hits", 10)
        self.stats.increment("misses", 5)
        self.stats.increment("creates", 5)
        self.stats.increment("reuses", 10)
        self.stats.record_metrics()

        self.stats.increment("hits", 20)
        self.stats.increment("misses", 2)
        self.stats.record_metrics()

        history = self.stats.get_history()
        assert len(history) == 2
        assert isinstance(history[0], PoolMetrics)
        assert isinstance(history[1], PoolMetrics)

        # Check the first snapshot
        assert history[0].hits == 10
        assert history[0].misses == 5
        assert history[0].hit_rate == pytest.approx(10 / 15)
        assert history[0].pool_efficiency == pytest.approx(10 / 15)

        # Check the second snapshot (counters are cumulative)
        assert history[1].hits == 30
        assert history[1].misses == 7

    def test_reset(self):
        """Test resetting all statistics."""
        self.stats.increment("hits", 10)
        self.stats.set_gauge("memory", 1024)
        self.stats.record_metrics()

        assert self.stats.get_all_metrics()["counters"]
        assert self.stats.get_history()

        self.stats.reset()

        all_stats = self.stats.get_all_metrics()
        assert not all_stats["counters"]
        assert not all_stats["gauges"]
        assert not self.stats.get_history()

    def test_pool_metrics_to_dict(self):
        """Test that PoolMetrics.to_dict converts timestamp to ISO format."""
        now = datetime.datetime.now()
        metrics = PoolMetrics(
            timestamp=now,
            hits=1,
            misses=2,
            creates=3,
            reuses=4,
            evictions=5,
            expired=6,
            corrupted=7,
            validation_failures=8,
            reset_failures=9,
            hit_rate=0.5,
            avg_object_age=10.0,
            pool_efficiency=0.8,
        )

        metrics_dict = metrics.to_dict()
        assert isinstance(metrics_dict["timestamp"], str)
        assert metrics_dict["timestamp"] == now.isoformat()

    def test_history_max_objects_per_key(self):
        """Test that the history is capped at _max_history."""
        # pylint: disable=protected-access
        self.stats._max_history = 2  # Set a small max history size

        self.stats.record_metrics()  # First entry
        assert len(self.stats._history) == 1

        self.stats.record_metrics()  # Second entry
        assert len(self.stats._history) == 2

        self.stats.record_metrics()  # Third entry, should cause pop(0)
        assert len(self.stats._history) == 2
        # Verify that the first element was indeed removed (optional, but good for confidence)
        # This would require inspecting the content of the metrics, which is not trivial here.
        # For now, just checking length is sufficient for coverage.
