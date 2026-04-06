"""
Thread-safe statistics management module for memory pool monitoring.

This module provides classes for tracking and recording detailed metrics
about memory pool performance, including hit rates, object lifecycle events,
and historical data collection in a thread-safe manner.
"""

import threading
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class PoolMetrics:  # pylint: disable=too-many-instance-attributes
    """
    A dataclass representing a snapshot of detailed pool metrics at a specific
    point in time. This is used to record historical performance and state of
    the memory pool.

    Attributes:
        timestamp (datetime): The exact date and time when these metrics were
            recorded.
        hits (int): The number of times an object was successfully retrieved
            from the pool (cache hit).
        misses (int): The number of times a new object had to be created
            because it wasn't in the pool (cache miss).
        creates (int): The total number of objects created by the pool's
            factory.
        reuses (int): The total number of times objects were reused from the
            pool.
        evictions (int): The number of objects removed from the pool due to
            LRU eviction.
        expired (int): The number of objects removed from the pool because
            they exceeded their TTL.
        corrupted (int): The number of objects detected as corrupted and
            destroyed.
        validation_failures (int): The number of times an object failed
            validation before being acquired or returned.
        reset_failures (int): The number of times an object failed to reset
            to its initial state.
        hit_rate (float): The ratio of hits to total requests (hits + misses),
            indicating pool efficiency.
        avg_object_age (float): The average age of objects currently in the
            pool (in seconds).
        pool_efficiency (float): A calculated metric representing the overall
            efficiency of the pool, typically based on reuse vs. creation.
    """

    timestamp: datetime
    hits: int
    misses: int
    creates: int
    reuses: int
    evictions: int
    expired: int
    corrupted: int
    validation_failures: int
    reset_failures: int
    hit_rate: float
    avg_object_age: float
    pool_efficiency: float

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the `PoolMetrics` instance into a dictionary, suitable for
        serialization. The timestamp is converted to ISO format for easy
        readability and compatibility.

        Returns:
            Dict[str, Any]: A dictionary representation of the metrics snapshot.
        """
        result = asdict(self)
        # Convert datetime to string for serialization
        result["timestamp"] = self.timestamp.isoformat()
        return result


class ThreadSafeStats:
    """
    A thread-safe statistics manager for the memory pool. It provides methods
    to increment counters, set gauge values, and record historical snapshots
    of various pool metrics. All operations are protected by a reentrant lock
    to ensure data consistency in a multi-threaded environment.
    """

    def __init__(self) -> None:
        """
        Initializes the ThreadSafeStats manager.
        """
        # Counter for various events (e.g., hits, misses, creates).
        self._counters: Counter[str] = Counter()
        # Dictionary for gauge metrics (e.g., current pool size, active objects).
        self._gauges: Dict[str, float] = {}
        # Reentrant lock for thread-safe access to internal data structures.
        self._lock = threading.RLock()
        # List to store historical `PoolMetrics` snapshots.
        self._history: List[PoolMetrics] = []
        # Maximum number of historical snapshots to retain.
        self._max_history = 1000

    def increment(self, key: str, value: int = 1) -> None:
        """
        Increments a specified counter by a given value. This operation is
        atomic.

        Args:
            key (str): The name of the counter to increment.
            value (int): The amount to increment the counter by. Defaults to 1.
        """
        with self._lock:
            self._counters[key] += value

    def increment_many(self, updates: Dict[str, int]) -> None:
        """
        Increments multiple counters atomically under a single lock acquisition.

        Args:
            updates (Dict[str, int]): Mapping of counter names to increment values.
        """
        with self._lock:
            for key, value in updates.items():
                self._counters[key] += value

    def set_gauge(self, key: str, value: float) -> None:
        """
        Sets the value of a specified gauge metric. This operation is atomic.

        Args:
            key (str): The name of the gauge to set.
            value (float): The new value for the gauge.
        """
        with self._lock:
            self._gauges[key] = value

    def get(self, key: str) -> int:
        """
        Retrieves the current value of a specified counter.

        Args:
            key (str): The name of the counter to retrieve.

        Returns:
            int: The current value of the counter. Returns 0 if the counter
                does not exist.
        """
        with self._lock:
            return self._counters[key]

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Retrieves all current counter and gauge statistics.

        Returns:
            Dict[str, Any]: A dictionary containing two keys: 'counters'
                (a dictionary of all counters) and 'gauges' (a dictionary
                of all gauges).
        """
        with self._lock:
            return {"counters": dict(self._counters), "gauges": dict(self._gauges)}

    def record_metrics(self) -> None:
        """
        Records a snapshot of the current pool metrics and adds it to the
        historical data. This method calculates derived metrics like hit rate
        and pool efficiency before storing.
        """
        with self._lock:
            total_requests = self._counters["hits"] + self._counters["misses"]
            hit_rate = self._counters["hits"] / total_requests if total_requests > 0 else 0

            efficiency = (
                self._counters["reuses"] / (self._counters["creates"] + self._counters["reuses"])
                if (self._counters["creates"] + self._counters["reuses"]) > 0
                else 0
            )

            metrics = PoolMetrics(
                timestamp=datetime.now(),
                hits=self._counters["hits"],
                misses=self._counters["misses"],
                creates=self._counters["creates"],
                reuses=self._counters["reuses"],
                evictions=self._counters["evictions"],
                expired=self._counters["expired"],
                corrupted=self._counters["corrupted"],
                validation_failures=self._counters["validation_failures"],
                reset_failures=self._counters["reset_failures"],
                hit_rate=hit_rate,
                avg_object_age=self._gauges.get("avg_object_age", 0),
                pool_efficiency=efficiency,
            )

            self._history.append(metrics)
            # Trim history to maintain the maximum size.
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def get_history(self, last_n: int = 100) -> List[PoolMetrics]:
        """
        Retrieves a portion of the historical metrics, specifically the most
        recent `last_n` snapshots.

        Args:
            last_n (int): The number of most recent historical snapshots to
                retrieve. Defaults to 100.

        Returns:
            List[PoolMetrics]: A list of `PoolMetrics` objects representing
                the historical data.
        """
        with self._lock:
            return self._history[-last_n:]

    def reset(self) -> None:
        """
        Resets all counters, gauges, and clears the historical metrics data.
        This effectively restarts the statistics collection.
        """
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._history.clear()
