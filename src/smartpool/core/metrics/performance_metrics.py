"""
Performance metrics module for memory pool monitoring and analysis.

This module provides comprehensive performance tracking capabilities for memory pools,
including acquisition time monitoring, hit rate calculation, lock contention analysis,
and throughput measurement. It supports detailed logging of individual acquisition
events and generates actionable alerts and recommendations.
"""

import statistics
import threading
import time
from collections import Counter, deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Generator, List, NamedTuple


class AcquisitionRecord(NamedTuple):
    """
    Represents a single record of an object acquisition from the memory pool.
    This detailed record is used for granular performance analysis.

    Attributes:
        timestamp (float): The Unix timestamp when the acquisition completed.
        acquisition_time_ms (float): The total time taken for the acquisition,
            in milliseconds.
        lock_wait_time_ms (float): The time spent waiting for the pool's main lock,
            in milliseconds.
        key (str): The key of the object that was acquired.
        hit (bool): True if the object was a pool hit (reused), False if it was
            a miss (newly created).
        validation_attempts (int): The number of validation attempts made for the
            object during acquisition.
    """

    timestamp: float
    acquisition_time_ms: float
    lock_wait_time_ms: float
    key: str
    hit: bool
    validation_attempts: int


@dataclass
class PerformanceSnapshot:  # pylint: disable=too-many-instance-attributes
    """
    A snapshot of the memory pool's performance metrics at a specific point in time.

    This dataclass aggregates various performance indicators, including acquisition
    times, hit rates, throughput, and lock contention, providing a comprehensive
    view of pool health.
    """

    timestamp: datetime

    # Basic metrics
    total_acquisitions: int
    hit_rate: float

    # Acquisition time statistics (in milliseconds)
    avg_acquisition_time_ms: float
    min_acquisition_time_ms: float
    max_acquisition_time_ms: float

    # Acquisition time percentiles (in milliseconds)
    p50_acquisition_time_ms: float
    p95_acquisition_time_ms: float
    p99_acquisition_time_ms: float

    # Lock contention metrics
    avg_lock_wait_time_ms: float
    max_lock_wait_time_ms: float
    lock_contention_rate: float  # % of acquisitions with wait > 1ms

    # Throughput and concurrency
    acquisitions_per_second: float
    peak_concurrent_acquisitions: int

    # Distribution by key
    top_keys_by_usage: List[tuple]  # (key, count)
    slowest_keys: List[tuple]  # (key, avg_time_ms)

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the PerformanceSnapshot instance into a dictionary, suitable for
        serialization (e.g., to JSON). The timestamp is converted to ISO format.

        Returns:
            Dict[str, Any]: A dictionary representation of the snapshot.
        """
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


class PerformanceMetrics:  # pylint: disable=too-many-instance-attributes
    """
    An advanced performance metrics system for the memory pool.

    This class collects, stores, and analyzes detailed acquisition data to provide
    insights into the pool's runtime behavior, identify bottlenecks, and generate
    performance reports.

    It tracks individual acquisition records, calculates various statistical measures,
    and can generate alerts and recommendations based on observed performance trends.
    """

    def __init__(self, history_size: int = 1000, enable_detailed_tracking: bool = True) -> None:
        """
        Initializes the PerformanceMetrics system.

        Args:
            history_size (int): The maximum number of `AcquisitionRecord` entries
                to keep in history. A larger size provides more historical data
                but consumes more memory.
            enable_detailed_tracking (bool): If True, enables detailed tracking of
                acquisition times, lock wait times, and per-key statistics.
                Disabling this can save memory if only high-level metrics are needed.
        """
        self.history_size = history_size
        self.enable_detailed_tracking = enable_detailed_tracking

        # Thread safety lock for concurrent access to metrics data.
        self._lock = threading.RLock()

        # A deque to store recent acquisition records. Limited by `history_size`.
        self._acquisition_history: deque[AcquisitionRecord] = deque(maxlen=history_size)

        # Real-time metrics for current concurrency and contention.
        self._active_acquisitions = 0
        self._peak_concurrent_acquisitions = 0
        self._lock_contention_events = 0
        self._total_lock_wait_time = 0.0

        # History of generated performance snapshots.
        self._performance_snapshots: deque[PerformanceSnapshot] = deque(maxlen=100)

        # Metrics aggregated by object key.
        self._key_usage_count: Counter = Counter()
        self._key_total_time: Dict[str, float] = {}

        # Timestamp of the last performance snapshot creation.
        self._last_snapshot_time = time.time()

    def mark_acquisition_start(self) -> None:
        """Track in-flight acquisitions for concurrency metrics."""
        with self._lock:
            self._active_acquisitions += 1
            self._peak_concurrent_acquisitions = max(
                self._peak_concurrent_acquisitions, self._active_acquisitions
            )

    def mark_acquisition_end(self) -> None:
        """Mark the end of an acquisition."""
        with self._lock:
            self._active_acquisitions = max(0, self._active_acquisitions - 1)

    @contextmanager
    def track_acquisition(self, key: str) -> Generator[Any, Any, Any]:
        """
        A context manager to track the duration and lock contention of an object
        acquisition.

        This method is intended to be used internally by the `GenericMemoryPool`'s
        `acquire` method.

        Args:
            key (str): The key of the object being acquired.

        Yields:
            None: The context manager yields control to the wrapped code block.
        """
        start_time = time.time()
        lock_start_time = None
        lock_wait_time = 0.0

        with self._lock:
            self._active_acquisitions += 1
            self._peak_concurrent_acquisitions = max(
                self._peak_concurrent_acquisitions, self._active_acquisitions
            )

        # Simulate waiting on the main pool lock
        lock_start_time = time.time()

        try:
            yield
        finally:
            end_time = time.time()

            if lock_start_time:
                lock_wait_time = (time.time() - lock_start_time) * 1000  # in ms

            acquisition_time = (end_time - start_time) * 1000  # in ms

            with self._lock:
                self._active_acquisitions -= 1

                if self.enable_detailed_tracking:
                    # Record the acquisition details.
                    record = AcquisitionRecord(
                        timestamp=end_time,
                        acquisition_time_ms=acquisition_time,
                        lock_wait_time_ms=lock_wait_time,
                        key=key,
                        hit=True,  # Updated by the pool's acquire method
                        validation_attempts=1,  # Updated by the pool's acquire method
                    )
                    self._acquisition_history.append(record)

                    # Update aggregated metrics by key.
                    self._update_key_metrics(key, acquisition_time, lock_wait_time)

    # pylint: disable=too-many-arguments
    def record_acquisition(
        self,
        key: str,
        acquisition_time_ms: float,
        hit: bool,
        *,
        validation_attempts: int = 1,
        lock_wait_time_ms: float = 0.0,
    ) -> None:
        """
        Manually records an object acquisition event.

        This method is typically called by the `GenericMemoryPool` after an object
        has been acquired, providing the final metrics.

        Args:
            key (str): The key of the object that was acquired.
            acquisition_time_ms (float): The total time taken for the acquisition,
                in milliseconds.
            hit (bool): True if the object was a pool hit (reused), False if it was
                a miss (newly created).
            validation_attempts (int): The number of validation attempts made for
                the object during acquisition.
            lock_wait_time_ms (float): The time spent waiting for the pool's main
                lock, in milliseconds.
        """
        with self._lock:
            if self.enable_detailed_tracking:
                record = AcquisitionRecord(
                    timestamp=time.time(),
                    acquisition_time_ms=acquisition_time_ms,
                    lock_wait_time_ms=lock_wait_time_ms,
                    key=key,
                    hit=hit,
                    validation_attempts=validation_attempts,
                )
                self._acquisition_history.append(record)

                # Update aggregated metrics by key.
                self._update_key_metrics(key, acquisition_time_ms, lock_wait_time_ms)

    def _update_key_metrics(
        self, key: str, acquisition_time_ms: float, lock_wait_time_ms: float
    ) -> None:
        """
        Updates the key-specific metrics with new acquisition data.

        Args:
            key (str): The key of the acquired object.
            acquisition_time_ms (float): The acquisition time in milliseconds.
            lock_wait_time_ms (float): The lock wait time in milliseconds.
        """
        self._key_usage_count[key] += 1
        if key not in self._key_total_time:
            self._key_total_time[key] = 0.0
        self._key_total_time[key] += acquisition_time_ms

        # Track lock contention events.
        if lock_wait_time_ms > 1.0:
            self._lock_contention_events += 1
        self._total_lock_wait_time += lock_wait_time_ms

    def create_snapshot(self) -> PerformanceSnapshot:
        """
        Generates a `PerformanceSnapshot` based on the current and historical
        acquisition data.

        This method calculates various statistical measures and aggregates them
        into a snapshot object, providing a comprehensive view of the pool's
        performance at the time of call.

        Returns:
            PerformanceSnapshot: An instance containing the calculated metrics.
                Returns an empty snapshot if no acquisition history is available.
        """
        with self._lock:
            current_time = datetime.now()

            if not self._acquisition_history:
                return self._create_empty_snapshot(current_time)

            history = list(self._acquisition_history)

            # Calculate basic metrics
            basic_metrics = self._calculate_basic_metrics(history)

            # Calculate time-based metrics
            time_metrics = self._calculate_time_metrics(history)

            # Calculate lock contention metrics
            lock_metrics = self._calculate_lock_metrics(history)

            # Calculate throughput metrics
            throughput_metrics = self._calculate_throughput_metrics(history)

            # Calculate key distribution metrics
            key_metrics = self._calculate_key_metrics()

            snapshot = PerformanceSnapshot(
                timestamp=current_time,
                **basic_metrics,
                **time_metrics,
                **lock_metrics,
                **throughput_metrics,
                **key_metrics,
            )

            self._performance_snapshots.append(snapshot)
            self._last_snapshot_time = time.time()

            return snapshot

    def _create_empty_snapshot(self, current_time: datetime) -> PerformanceSnapshot:
        """Creates an empty snapshot when no history is available."""
        return PerformanceSnapshot(
            timestamp=current_time,
            total_acquisitions=0,
            hit_rate=0.0,
            avg_acquisition_time_ms=0.0,
            min_acquisition_time_ms=0.0,
            max_acquisition_time_ms=0.0,
            p50_acquisition_time_ms=0.0,
            p95_acquisition_time_ms=0.0,
            p99_acquisition_time_ms=0.0,
            avg_lock_wait_time_ms=0.0,
            max_lock_wait_time_ms=0.0,
            lock_contention_rate=0.0,
            acquisitions_per_second=0.0,
            peak_concurrent_acquisitions=0,
            top_keys_by_usage=[],
            slowest_keys=[],
        )

    def _calculate_basic_metrics(self, history: List[AcquisitionRecord]) -> Dict[str, Any]:
        """Calculates basic metrics from the acquisition history."""
        hit_count = sum(1 for r in history if r.hit)
        return {
            "total_acquisitions": len(history),
            "hit_rate": hit_count / len(history) if history else 0.0,
        }

    def _calculate_time_metrics(self, history: List[AcquisitionRecord]) -> Dict[str, Any]:
        """Calculates time-based metrics from the acquisition history."""
        acquisition_times = [r.acquisition_time_ms for r in history]

        if not acquisition_times:
            return {
                "avg_acquisition_time_ms": 0.0,
                "min_acquisition_time_ms": 0.0,
                "max_acquisition_time_ms": 0.0,
                "p50_acquisition_time_ms": 0.0,
                "p95_acquisition_time_ms": 0.0,
                "p99_acquisition_time_ms": 0.0,
            }

        sorted_times = sorted(acquisition_times)
        n = len(sorted_times)

        return {
            "avg_acquisition_time_ms": statistics.mean(acquisition_times),
            "min_acquisition_time_ms": min(acquisition_times),
            "max_acquisition_time_ms": max(acquisition_times),
            "p50_acquisition_time_ms": sorted_times[n // 2],
            "p95_acquisition_time_ms": sorted_times[int(n * 0.95)],
            "p99_acquisition_time_ms": sorted_times[int(n * 0.99)],
        }

    def _calculate_lock_metrics(self, history: List[AcquisitionRecord]) -> Dict[str, Any]:
        """Calculates lock contention metrics from the acquisition history."""
        lock_wait_times = [r.lock_wait_time_ms for r in history]
        contention_events = sum(1 for t in lock_wait_times if t > 1.0)

        return {
            "avg_lock_wait_time_ms": (statistics.mean(lock_wait_times) if lock_wait_times else 0.0),
            "max_lock_wait_time_ms": max(lock_wait_times) if lock_wait_times else 0.0,
            "lock_contention_rate": contention_events / len(history) if history else 0.0,
        }

    def _calculate_throughput_metrics(self, history: List[AcquisitionRecord]) -> Dict[str, Any]:
        """Calculates throughput metrics from the acquisition history."""
        now = time.time()
        if not history:
            acquisitions_per_second = 0.0
        else:
            recent_window_start = max(history[0].timestamp, now - 60.0)
            recent_acquisitions = [r for r in history if r.timestamp >= recent_window_start]
            window_duration = max(1e-6, now - recent_window_start)
            acquisitions_per_second = len(recent_acquisitions) / window_duration

        return {
            "acquisitions_per_second": acquisitions_per_second,
            "peak_concurrent_acquisitions": self._peak_concurrent_acquisitions,
        }

    def _calculate_key_metrics(self) -> Dict[str, Any]:
        """Calculates key distribution metrics."""
        top_keys_by_usage = self._key_usage_count.most_common(5)

        slowest_keys = []
        for key, total_time in self._key_total_time.items():
            if key in self._key_usage_count:
                avg_time = total_time / self._key_usage_count[key]
                slowest_keys.append((key, avg_time))
        slowest_keys = sorted(slowest_keys, key=lambda x: x[1], reverse=True)[:5]

        return {
            "top_keys_by_usage": top_keys_by_usage,
            "slowest_keys": slowest_keys,
        }

    def get_performance_report(self, last_n_snapshots: int = 10) -> Dict[str, Any]:
        """
        Generates a comprehensive performance report, including current metrics,
        historical trends, and actionable alerts and recommendations.

        Args:
            last_n_snapshots (int): The number of most recent snapshots to include
                in trend analysis.

        Returns:
            Dict[str, Any]: A dictionary containing the performance report.
        """
        with self._lock:
            current_snapshot = self.create_snapshot()
            recent_snapshots = list(self._performance_snapshots)[-last_n_snapshots:]

            if not recent_snapshots:
                recent_snapshots = [current_snapshot]

            # Calculate trends from recent snapshots.
            trends = self._calculate_trends(recent_snapshots)

            return {
                "current_metrics": current_snapshot.to_dict(),
                "trends": trends,
                "alerts": self._generate_alerts(current_snapshot),
                "recommendations": self._generate_recommendations(current_snapshot),
            }

    def _calculate_trends(self, snapshots: List[PerformanceSnapshot]) -> Dict[str, List[float]]:
        """Calculates trends from a list of performance snapshots."""
        return {
            "hit_rate_trend": [s.hit_rate for s in snapshots],
            "avg_response_time_trend": [s.avg_acquisition_time_ms for s in snapshots],
            "throughput_trend": [s.acquisitions_per_second for s in snapshots],
        }

    def _generate_alerts(self, snapshot: PerformanceSnapshot) -> List[Dict[str, Any]]:
        """
        Analyzes a `PerformanceSnapshot` and generates a list of alerts for
        detected performance issues.

        Args:
            snapshot (PerformanceSnapshot): The performance snapshot to analyze.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing an alert.
        """
        alerts = []

        # Alert for low hit rate.
        if snapshot.hit_rate < 0.5:
            alerts.append(
                {
                    "level": "warning",
                    "metric": "hit_rate",
                    "message": f"Low hit rate ({snapshot.hit_rate:.1%}). "
                    f"Consider increasing pool size.",
                    "value": snapshot.hit_rate,
                }
            )

        # Alert for high response time (P95).
        if snapshot.p95_acquisition_time_ms > 50.0:
            alerts.append(
                {
                    "level": "warning",
                    "metric": "response_time",
                    "message": f"High P95 acquisition time "
                    f"({snapshot.p95_acquisition_time_ms:.1f}ms).",
                    "value": snapshot.p95_acquisition_time_ms,
                }
            )

        # Alert for high lock contention.
        if snapshot.lock_contention_rate > 0.3:
            alerts.append(
                {
                    "level": "critical",
                    "metric": "lock_contention",
                    "message": f"High contention ({snapshot.lock_contention_rate:.1%}). "
                    f"Optimize concurrency.",
                    "value": snapshot.lock_contention_rate,
                }
            )

        # Alert for low throughput (if there's significant activity).
        if snapshot.acquisitions_per_second < 10.0 and snapshot.total_acquisitions > 100:
            alerts.append(
                {
                    "level": "info",
                    "metric": "throughput",
                    "message": f"Low throughput ({snapshot.acquisitions_per_second:.1f} ops/sec).",
                    "value": snapshot.acquisitions_per_second,
                }
            )

        return alerts

    def _generate_recommendations(self, snapshot: PerformanceSnapshot) -> List[str]:
        """
        Generates a list of optimization recommendations based on the provided
        performance snapshot.

        Args:
            snapshot (PerformanceSnapshot): The performance snapshot to analyze.

        Returns:
            List[str]: A list of optimization recommendations.
        """
        recommendations = []

        if snapshot.hit_rate < 0.6:
            recommendations.append(
                "Increase pool size (max_objects_per_key) or object lifespan (ttl_seconds) "
                "to improve hit rate."
            )

        if snapshot.lock_contention_rate > 0.2:
            recommendations.append(
                "Reduce validation attempts or optimize cleanup frequency "
                "to decrease lock contention."
            )

        if snapshot.p99_acquisition_time_ms > 100.0:
            recommendations.append(
                "Consider pre-warming the pool or implementing asynchronous "
                "validation for faster acquisitions."
            )

        if snapshot.top_keys_by_usage:
            top_key, usage = snapshot.top_keys_by_usage[0]
            recommendations.append(
                f"Key '{top_key}' is heavily used ({usage} times). "
                f"Consider specific configuration or a dedicated pool for this key."
            )

        return recommendations

    def reset_metrics(self) -> None:
        """
        Resets all collected performance metrics and history. This is useful for
        starting a new measurement period or for testing purposes.
        """
        with self._lock:
            self._acquisition_history.clear()
            self._performance_snapshots.clear()
            self._key_usage_count.clear()
            self._key_total_time.clear()
            self._active_acquisitions = 0
            self._peak_concurrent_acquisitions = 0
            self._lock_contention_events = 0
            self._total_lock_wait_time = 0.0
            self._last_snapshot_time = time.time()

    def get_key_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves detailed performance statistics aggregated by object key.

        This provides insights into which types of objects (identified by their key)
        are most frequently used, their average acquisition times, and hit rates.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary where keys are object keys,
                and values are dictionaries containing statistics for that key.
        """
        with self._lock:
            stats_by_key = {}

            for key, usage_count in self._key_usage_count.items():
                total_time = self._key_total_time.get(key, 0.0)
                avg_time = total_time / usage_count if usage_count > 0 else 0.0

                # Retrieve acquisition times specifically for this key.
                key_times = [
                    r.acquisition_time_ms for r in self._acquisition_history if r.key == key
                ]

                stats_by_key[key] = {
                    "usage_count": usage_count,
                    "total_time_ms": total_time,
                    "avg_time_ms": avg_time,
                    "min_time_ms": min(key_times) if key_times else 0.0,
                    "max_time_ms": max(key_times) if key_times else 0.0,
                    "hit_rate": self._calculate_key_hit_rate(key),
                }

            return stats_by_key

    def _calculate_key_hit_rate(self, key: str) -> float:
        """Calculates the hit rate for a specific key from available history."""
        key_records = [r for r in self._acquisition_history if r.key == key]
        if not key_records:
            return 0.0

        hits = sum(1 for r in key_records if r.hit)
        return hits / len(key_records)
