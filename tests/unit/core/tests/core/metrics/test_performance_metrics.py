"""Tests for the PerformanceMetrics class and related functionalities."""

import time

import pytest

from smartpool.core.metrics.performance_metrics import (
    AcquisitionRecord,
    PerformanceMetrics,
    PerformanceSnapshot,
)


# pylint: disable=protected-access, W0201, R0904
class TestPerformanceMetrics:
    """Tests for the PerformanceMetrics class."""

    def setup_method(self):
        """Set up for each test method."""
        self.metrics = PerformanceMetrics(history_size=100)

    def test_record_acquisition(self):
        """Test recording a single acquisition event."""
        self.metrics.record_acquisition(
            key="test_key",
            acquisition_time_ms=10.5,
            hit=True,
            validation_attempts=1,
            lock_wait_time_ms=0.5,
        )
        assert len(self.metrics._acquisition_history) == 1
        record = self.metrics._acquisition_history[0]
        assert record.key == "test_key"
        assert record.acquisition_time_ms == 10.5
        assert record.hit
        assert record.validation_attempts == 1
        assert record.lock_wait_time_ms == 0.5

    def test_track_acquisition_context_manager(self):
        """Test the track_acquisition context manager's direct effects."""
        key = "context_key"
        initial_active_acquisitions = self.metrics._active_acquisitions
        initial_peak_concurrent_acquisitions = self.metrics._peak_concurrent_acquisitions
        initial_history_len = len(self.metrics._acquisition_history)

        with self.metrics.track_acquisition(key=key):
            # Inside the context, active acquisitions should increase
            assert self.metrics._active_acquisitions == initial_active_acquisitions + 1
            assert self.metrics._peak_concurrent_acquisitions >= (
                initial_peak_concurrent_acquisitions + 1
            )
            time.sleep(0.01)  # Simulate some work

        # After the context, active acquisitions should return to initial state
        assert self.metrics._active_acquisitions == initial_active_acquisitions

        # Verify that an AcquisitionRecord was added by the context manager
        assert len(self.metrics._acquisition_history) == initial_history_len + 1
        record = self.metrics._acquisition_history[-1]  # Get the last added record
        assert record.key == key
        assert record.acquisition_time_ms > 0
        assert record.lock_wait_time_ms >= 0  # Can be 0 if no actual wait
        assert record.hit  # Default value from context manager
        assert record.validation_attempts == 1  # Default value from context manager
        assert record.timestamp > 0  # Check if timestamp is set

    def test_detailed_tracking_disabled(self):
        """Test that no detailed tracking occurs when enable_detailed_tracking is False."""
        metrics_no_tracking = PerformanceMetrics(enable_detailed_tracking=False)

        metrics_no_tracking.record_acquisition(
            key="no_track_key",
            acquisition_time_ms=5.0,
            hit=True,
            validation_attempts=1,
            lock_wait_time_ms=0.1,
        )

        with metrics_no_tracking.track_acquisition(key="no_track_context_key"):
            time.sleep(0.005)

        assert len(metrics_no_tracking._acquisition_history) == 0
        assert len(metrics_no_tracking._key_usage_count) == 0
        assert len(metrics_no_tracking._key_total_time) == 0
        assert metrics_no_tracking._lock_contention_events == 0
        assert metrics_no_tracking._total_lock_wait_time == 0.0

    def test_create_snapshot_with_data(self):
        """Test creating a performance snapshot from recorded data."""
        # Record some data
        self.metrics.record_acquisition("key1", 10, True)
        self.metrics.record_acquisition("key1", 20, False)  # miss
        self.metrics.record_acquisition("key2", 30, True)

        snapshot = self.metrics.create_snapshot()

        assert isinstance(snapshot, PerformanceSnapshot)
        assert snapshot.total_acquisitions == 3
        assert snapshot.hit_rate == pytest.approx(2 / 3)
        assert snapshot.avg_acquisition_time_ms == pytest.approx(20.0)
        assert snapshot.min_acquisition_time_ms == 10.0
        assert snapshot.max_acquisition_time_ms == 30.0
        assert ("key1", 2) in snapshot.top_keys_by_usage

    def test_create_snapshot_with_no_data(self):
        """Test creating a snapshot when no data has been recorded."""
        snapshot = self.metrics.create_snapshot()
        assert snapshot.total_acquisitions == 0
        assert snapshot.hit_rate == 0.0
        assert snapshot.avg_acquisition_time_ms == 0.0

    def test_generate_alerts(self):
        """Test the generation of performance alerts based on metrics."""
        # Simulate low hit rate
        snapshot_low_hit = self.metrics.create_snapshot()
        snapshot_low_hit.hit_rate = 0.4
        alerts = self.metrics._generate_alerts(snapshot_low_hit)
        assert any(a["metric"] == "hit_rate" for a in alerts)

        # Simulate high response time
        snapshot_high_latency = self.metrics.create_snapshot()
        snapshot_high_latency.p95_acquisition_time_ms = 100.0
        alerts = self.metrics._generate_alerts(snapshot_high_latency)
        assert any(a["metric"] == "response_time" for a in alerts)

    def test_generate_alerts_high_lock_contention(self):
        """Test that a critical alert is generated for high lock contention."""
        # Record 10 acquisitions, with 4 having high lock wait time
        for i in range(10):
            self.metrics.record_acquisition(
                key=f"key_{i}",
                acquisition_time_ms=10.0,
                hit=True,
                validation_attempts=1,
                lock_wait_time_ms=5.0 if i % 2 == 0 and i < 8 else 0.0,  # 4 contention events
            )

        snapshot = self.metrics.create_snapshot()
        alerts = self.metrics._generate_alerts(snapshot)

        found_alert = False
        for alert in alerts:
            if alert["metric"] == "lock_contention" and alert["level"] == "critical":
                found_alert = True
                break
        assert found_alert, "Critical lock contention alert not found."
        assert snapshot.lock_contention_rate > 0.3

    def test_generate_alerts_low_throughput(self):
        """
        Test that an info alert is generated for low
        throughput with sufficient total acquisitions.
        """
        # Create metrics with larger history size to ensure we can store 101+ records
        metrics_large = PerformanceMetrics(history_size=200)

        now = time.time()

        # Directly populate the acquisition history with records having the desired timestamps
        # 97 old acquisitions (older than 60 seconds) to ensure total > 100
        for i in range(97):
            timestamp = now - 70.0 + (i * 0.1)  # From 70 seconds ago to 60.3 seconds ago
            record = AcquisitionRecord(
                timestamp=timestamp,
                acquisition_time_ms=1.0,
                lock_wait_time_ms=0.0,
                key=f"old_key_{i}",
                hit=True,
                validation_attempts=1,
            )
            metrics_large._acquisition_history.append(record)
            metrics_large._key_usage_count[f"old_key_{i}"] += 1
            metrics_large._key_total_time[f"old_key_{i}"] = (
                metrics_large._key_total_time.get(f"old_key_{i}", 0.0) + 1.0
            )

        # 5 recent acquisitions (within last 60 seconds)
        for i in range(5):
            timestamp = now - 5.0 + (i * 0.1)  # From 5 seconds ago to 4.6 seconds ago
            record = AcquisitionRecord(
                timestamp=timestamp,
                acquisition_time_ms=1.0,
                lock_wait_time_ms=0.0,
                key=f"recent_key_{i}",
                hit=True,
                validation_attempts=1,
            )
            metrics_large._acquisition_history.append(record)
            metrics_large._key_usage_count[f"recent_key_{i}"] += 1
            metrics_large._key_total_time[f"recent_key_{i}"] = (
                metrics_large._key_total_time.get(f"recent_key_{i}", 0.0) + 1.0
            )

        # Set _last_snapshot_time to simulate elapsed time for throughput calculation
        metrics_large._last_snapshot_time = now - 10.0

        snapshot = metrics_large.create_snapshot()
        alerts = metrics_large._generate_alerts(snapshot)

        found_alert = False
        for alert in alerts:
            if alert["metric"] == "throughput" and alert["level"] == "info":
                found_alert = True
                break

        assert found_alert, (
            f"Low throughput alert not found. Throughput:"
            f" {snapshot.acquisitions_per_second},"
            f" Total: {snapshot.total_acquisitions}"
        )
        assert snapshot.acquisitions_per_second < 10.0
        assert snapshot.total_acquisitions > 100

    def test_generate_alerts_high_response_time(self):
        """Test that a warning alert is generated for high P95 response time."""
        # Record acquisitions with times that will result in P95 > 50ms
        acquisition_times = [10.0, 20.0, 30.0, 40.0, 45.0, 48.0, 52.0, 60.0, 70.0, 80.0]
        for i, time_ms in enumerate(acquisition_times):
            self.metrics.record_acquisition(
                key=f"slow_key_{i}",
                acquisition_time_ms=time_ms,
                hit=True,
                validation_attempts=1,
                lock_wait_time_ms=0.0,
            )

        snapshot = self.metrics.create_snapshot()
        alerts = self.metrics._generate_alerts(snapshot)

        found_alert = False
        for alert in alerts:
            if alert["metric"] == "response_time" and alert["level"] == "warning":
                found_alert = True
                break

        assert found_alert, (
            f"High response time alert not found. P95: {snapshot.p95_acquisition_time_ms}"
        )
        assert snapshot.p95_acquisition_time_ms > 50.0

    def test_generate_recommendations(self):
        """Test the generation of optimization recommendations."""
        # Simulate low hit rate
        snapshot_low_hit = self.metrics.create_snapshot()
        snapshot_low_hit.hit_rate = 0.5
        recs = self.metrics._generate_recommendations(snapshot_low_hit)
        assert any("Increase pool size" in r for r in recs)

    def test_get_performance_report(self):
        """Test the full performance report structure."""
        self.metrics.record_acquisition("key1", 15, True)
        report = self.metrics.get_performance_report()

        assert "current_metrics" in report
        assert "trends" in report
        assert "alerts" in report
        assert "recommendations" in report
        assert report["current_metrics"]["total_acquisitions"] == 1

    def test_get_performance_report_with_no_snapshots(self):
        """Test get_performance_report when no snapshots have been recorded."""
        # Ensure _performance_snapshots is empty
        self.metrics._performance_snapshots.clear()
        report = self.metrics.get_performance_report()

        assert "current_metrics" in report
        assert "trends" in report
        assert "alerts" in report
        assert "recommendations" in report
        # The current_metrics should be an empty snapshot as no acquisitions were made
        assert report["current_metrics"]["total_acquisitions"] == 0
        # The trends should contain only the current (empty) snapshot's data
        assert len(report["trends"]["hit_rate_trend"]) == 1
        assert report["trends"]["hit_rate_trend"][0] == 0.0

    def test_record_acquisition_lock_contention(self):
        """Test that lock_contention_events is incremented when lock_wait_time_ms > 1.0."""
        initial_contention_events = self.metrics._lock_contention_events

        self.metrics.record_acquisition(
            key="contention_key",
            acquisition_time_ms=100.0,
            hit=True,
            validation_attempts=1,
            lock_wait_time_ms=5.0,  # This should trigger the contention event
        )

        assert self.metrics._lock_contention_events == initial_contention_events + 1

    def test_reset_metrics(self):
        """Test resetting all collected metrics."""
        self.metrics.record_acquisition("key1", 10, True)
        assert len(self.metrics._acquisition_history) > 0

        self.metrics.reset_metrics()

        assert len(self.metrics._acquisition_history) == 0
        assert len(self.metrics._key_usage_count) == 0
        assert self.metrics._active_acquisitions == 0

    def test_get_key_statistics(self):
        """Test detailed statistics aggregation by key."""
        self.metrics.record_acquisition("keyA", 10, True)
        self.metrics.record_acquisition("keyB", 20, False)
        self.metrics.record_acquisition("keyA", 15, True)

        key_stats = self.metrics.get_key_statistics()

        assert "keyA" in key_stats
        assert "keyB" in key_stats
        assert key_stats["keyA"]["usage_count"] == 2
        assert key_stats["keyA"]["avg_time_ms"] == pytest.approx(12.5)
        assert key_stats["keyA"]["hit_rate"] == 1.0
        assert key_stats["keyB"]["usage_count"] == 1
        assert key_stats["keyB"]["hit_rate"] == 0.0

    def test_get_key_statistics_with_empty_key_times(self):
        """Test get_key_statistics when a key has no acquisition records."""
        # Ensure _acquisition_history is empty
        self.metrics._acquisition_history.clear()
        # Manually add a key to usage count without any acquisition records
        self.metrics._key_usage_count["empty_key"] = 1

        key_stats = self.metrics.get_key_statistics()

        assert "empty_key" in key_stats
        assert key_stats["empty_key"]["usage_count"] == 1
        assert key_stats["empty_key"]["total_time_ms"] == 0.0
        assert key_stats["empty_key"]["avg_time_ms"] == 0.0
        assert key_stats["empty_key"]["min_time_ms"] == 0.0
        assert key_stats["empty_key"]["max_time_ms"] == 0.0
        assert key_stats["empty_key"]["hit_rate"] == 0.0

    def test_get_key_statistics_with_partial_empty_key_times(self):
        """Test get_key_statistics when some keys have empty key_times lists.

        This test specifically targets lines 449 and 454 to ensure 100% coverage.
        """
        # Add a record for key1
        self.metrics.record_acquisition("key1", 25.0, True)

        # Manually add key2 to counters but ensure no records exist for it in history
        self.metrics._key_usage_count["key2"] = 3
        self.metrics._key_total_time["key2"] = 60.0

        # Clear acquisition history so key2 will have empty key_times
        # but keep the counters
        original_key1_count = self.metrics._key_usage_count["key1"]
        original_key1_time = self.metrics._key_total_time["key1"]

        self.metrics._acquisition_history.clear()

        # Restore key1 counters manually
        self.metrics._key_usage_count["key1"] = original_key1_count
        self.metrics._key_total_time["key1"] = original_key1_time

        key_stats = self.metrics.get_key_statistics()

        # Both keys should be present
        assert "key1" in key_stats
        assert "key2" in key_stats

        # key1 should have empty key_times (lines 449, 454)
        assert key_stats["key1"]["min_time_ms"] == 0.0
        assert key_stats["key1"]["max_time_ms"] == 0.0

        # key2 should also have empty key_times
        assert key_stats["key2"]["min_time_ms"] == 0.0
        assert key_stats["key2"]["max_time_ms"] == 0.0
        assert key_stats["key2"]["avg_time_ms"] == pytest.approx(20.0)  # 60.0 / 3

    def test_generate_recommendations_lock_contention(self):
        """Test generation of lock contention recommendation when contention rate > 0.2."""
        # Create a snapshot with high lock contention rate
        snapshot = self.metrics.create_snapshot()
        snapshot.lock_contention_rate = 0.25  # > 0.2 to trigger the recommendation

        recommendations = self.metrics._generate_recommendations(snapshot)

        found_recommendation = False
        for rec in recommendations:
            if "Reduce validation attempts or optimize cleanup frequency" in rec:
                found_recommendation = True
                break

        assert found_recommendation, "Lock contention recommendation not found"

    def test_generate_recommendations_high_p99_time(self):
        """Test generation of P99 acquisition time recommendation when P99 > 100.0ms."""
        # Create a snapshot with high P99 acquisition time
        snapshot = self.metrics.create_snapshot()
        snapshot.p99_acquisition_time_ms = 150.0  # > 100.0 to trigger the recommendation

        recommendations = self.metrics._generate_recommendations(snapshot)

        found_recommendation = False
        for rec in recommendations:
            if "Consider pre-warming the pool or implementing asynchronous validation" in rec:
                found_recommendation = True
                break

        assert found_recommendation, "High P99 time recommendation not found"

    def test_calculate_time_metrics(self):
        """Test calculation time metrics when list is empty."""
        res = self.metrics._calculate_time_metrics([])
        assert res["avg_acquisition_time_ms"] == 0.0
        assert res["min_acquisition_time_ms"] == 0.0
        assert res["max_acquisition_time_ms"] == 0.0
        assert res["p50_acquisition_time_ms"] == 0.0
        assert res["p95_acquisition_time_ms"] == 0.0
        assert res["p99_acquisition_time_ms"] == 0.0

    def test_calculate_throughput_metrics_with_empty_history(self):
        """Test throughput calculation path when there is no acquisition history."""
        res = self.metrics._calculate_throughput_metrics([])
        assert res["acquisitions_per_second"] == 0.0
        assert res["peak_concurrent_acquisitions"] == self.metrics._peak_concurrent_acquisitions

    def test_calculate_key_hit_rate(self):
        """Test calculation key hit rate when key has no recorded history."""
        res = self.metrics._calculate_key_hit_rate("toto")
        assert res == 0.0
