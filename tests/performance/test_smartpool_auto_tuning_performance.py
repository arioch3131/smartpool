"""
Performance tests for SmartObjectManager comparing auto-tuning vs. no auto-tuning.
Extended version with longer-duration tests.
"""

import time

import pytest

from examples.factories import BytesIOFactory
from smartpool import SmartObjectManager
from smartpool.config import (
    MemoryConfig,
    MemoryConfigFactory,
    MemoryPressure,
    ObjectCreationCost,
    PoolConfiguration,
)


class TestSmartPoolAutoTuningPerformance:
    """
    Performance tests to compare SmartObjectManager with and without auto-tuning.
    Extended version with longer test duration and more comprehensive scenarios.
    """

    @pytest.fixture(scope="class")
    def base_pool_config(self):
        """Fixture to provide a base MemoryConfig for testing."""
        return MemoryConfig(
            max_objects_per_key=50,
            ttl_seconds=300.0,
            cleanup_interval_seconds=60.0,
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
            enable_lock_contention_tracking=True,
            max_expected_concurrency=20,
            object_creation_cost=ObjectCreationCost.MEDIUM,
            memory_pressure=MemoryPressure.NORMAL,
        )

    @pytest.fixture(scope="class")
    def no_auto_tune_pool(self, base_pool_config):
        """Fixture for a SmartObjectManager without auto-tuning (fixed config)."""
        factory = BytesIOFactory()
        pool = SmartObjectManager(
            factory=factory,
            default_config=base_pool_config,
            pool_config=PoolConfiguration(register_atexit=False),
        )
        yield pool
        pool.shutdown()

    @pytest.fixture(scope="class")
    def auto_tune_pool(self, base_pool_config):
        """Fixture for a SmartObjectManager with auto-tuning applied."""
        factory = BytesIOFactory()

        # Simulate observed metrics that would trigger auto-tuning adjustments
        # For example, low hit rate, high acquisition time, high contention
        observed_metrics = {
            "hit_rate": 0.2,  # Low hit rate
            "avg_acquisition_time_ms": 15.0,  # High acquisition time
            "lock_contention_rate": 0.4,  # High contention
        }

        tuned_config = MemoryConfigFactory.auto_tune_config(
            base_config=base_pool_config, observed_metrics=observed_metrics
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=tuned_config,
            pool_config=PoolConfiguration(register_atexit=False),
        )
        yield pool
        pool.shutdown()

    def _run_acquire_release_benchmark(self, pool, benchmark):
        """Helper to benchmark acquire/release operations."""
        # Pre-fill the pool to ensure objects are available for reuse
        pre_acquired = []
        for _ in range(pool.default_config.max_objects_per_key):
            obj_id, key, obj = pool.acquire()
            pre_acquired.append((obj_id, key, obj))
        for obj_id, key, obj in pre_acquired:
            pool.release(obj_id, key, obj)

        def acquire_release():
            obj_id, key, obj = pool.acquire()
            pool.release(obj_id, key, obj)

        benchmark(acquire_release)

    def test_acquire_release_performance_no_auto_tune(self, no_auto_tune_pool, benchmark):
        """Measure acquire/release performance without auto-tuning."""
        self._run_acquire_release_benchmark(no_auto_tune_pool, benchmark)

    def test_acquire_release_performance_with_auto_tune(self, auto_tune_pool, benchmark):
        """Measure acquire/release performance with auto-tuning."""
        self._run_acquire_release_benchmark(auto_tune_pool, benchmark)

    def _run_object_creation_benchmark(self, pool, benchmark):
        """Helper to benchmark object creation when pool is exhausted."""
        acquired_objects = []
        for _ in range(pool.default_config.max_objects_per_key):
            obj_id, key, obj = pool.acquire()
            acquired_objects.append((obj_id, key, obj))

        def create_new_object():
            obj_id, key, obj = pool.acquire()
            pool.release(obj_id, key, obj)

        benchmark(create_new_object)

        for obj_id, key, obj in acquired_objects:
            pool.release(obj_id, key, obj)

    def test_object_creation_performance_no_auto_tune(self, no_auto_tune_pool, benchmark):
        """Measure object creation performance without auto-tuning."""
        self._run_object_creation_benchmark(no_auto_tune_pool, benchmark)

    def test_object_creation_performance_with_auto_tune(self, auto_tune_pool, benchmark):
        """Measure object creation performance with auto-tuning."""
        self._run_object_creation_benchmark(auto_tune_pool, benchmark)

    # Extended duration tests
    def _run_extended_mixed_workload_benchmark(self, pool, benchmark, duration_seconds=5.0):
        """Extended benchmark with mixed acquire/release and creation patterns."""

        def mixed_workload():
            start_time = time.time()
            operations_count = 0

            while time.time() - start_time < duration_seconds:
                # Cycle through different workload patterns
                cycle = operations_count % 4

                if cycle == 0:
                    # Standard acquire/release
                    obj_id, key, obj = pool.acquire()
                    pool.release(obj_id, key, obj)
                elif cycle == 1:
                    # Acquire multiple, then release all
                    acquired = []
                    for _ in range(3):
                        obj_id, key, obj = pool.acquire()
                        acquired.append((obj_id, key, obj))
                    for obj_id, key, obj in acquired:
                        pool.release(obj_id, key, obj)
                elif cycle == 2:
                    # Hold objects briefly
                    obj_id, key, obj = pool.acquire()
                    time.sleep(0.001)  # Brief hold
                    pool.release(obj_id, key, obj)
                else:
                    # Burst acquisition
                    for _ in range(5):
                        obj_id, key, obj = pool.acquire()
                        pool.release(obj_id, key, obj)

                operations_count += 1

        benchmark.pedantic(mixed_workload, rounds=3, iterations=1)

    def test_extended_mixed_workload_no_auto_tune(self, no_auto_tune_pool, benchmark):
        """Extended mixed workload test without auto-tuning (5 seconds duration)."""
        self._run_extended_mixed_workload_benchmark(no_auto_tune_pool, benchmark, 5.0)

    def test_extended_mixed_workload_with_auto_tune(self, auto_tune_pool, benchmark):
        """Extended mixed workload test with auto-tuning (5 seconds duration)."""
        self._run_extended_mixed_workload_benchmark(auto_tune_pool, benchmark, 5.0)

    def _run_long_duration_stress_test(self, pool, benchmark, duration_seconds=10.0):
        """Long duration stress test with high concurrency simulation."""

        def stress_workload():
            start_time = time.time()
            concurrent_objects = []
            max_concurrent = 15

            while time.time() - start_time < duration_seconds:
                # Maintain concurrent objects at max level
                while len(concurrent_objects) < max_concurrent:
                    obj_id, key, obj = pool.acquire()
                    concurrent_objects.append((obj_id, key, obj, time.time()))

                # Randomly release some objects (simulate real usage)
                if len(concurrent_objects) > 0:
                    # Release objects held for more than 0.01 seconds
                    current_time = time.time()
                    to_release = []
                    for i, (obj_id, key, obj, acquired_time) in enumerate(concurrent_objects):
                        if current_time - acquired_time > 0.01:
                            to_release.append(i)

                    # Release from end to beginning to maintain indices
                    for i in reversed(to_release):
                        obj_id, key, obj, _ = concurrent_objects.pop(i)
                        pool.release(obj_id, key, obj)

                # Small delay to prevent tight loop
                time.sleep(0.001)

            # Release all remaining objects
            for obj_id, key, obj, _ in concurrent_objects:
                pool.release(obj_id, key, obj)

        benchmark.pedantic(stress_workload, rounds=2, iterations=1)

    def test_long_duration_stress_no_auto_tune(self, no_auto_tune_pool, benchmark):
        """Long duration stress test without auto-tuning (10 seconds)."""
        self._run_long_duration_stress_test(no_auto_tune_pool, benchmark, 10.0)

    def test_long_duration_stress_with_auto_tune(self, auto_tune_pool, benchmark):
        """Long duration stress test with auto-tuning (10 seconds)."""
        self._run_long_duration_stress_test(auto_tune_pool, benchmark, 10.0)

    def _run_endurance_test(self, pool, benchmark, duration_seconds=15.0):
        """Endurance test to measure performance degradation over time."""

        def endurance_workload():
            start_time = time.time()
            total_operations = 0
            operation_times = []

            while time.time() - start_time < duration_seconds:
                op_start = time.time()

                # Perform a standard operation
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

                op_end = time.time()
                operation_times.append(op_end - op_start)
                total_operations += 1

                # Every 100 operations, check for performance degradation
                if total_operations % 100 == 0:
                    recent_avg = sum(operation_times[-10:]) / min(10, len(operation_times))
                    overall_avg = sum(operation_times) / len(operation_times)

                    # Log significant degradation (for debugging)
                    if recent_avg > overall_avg * 1.5:
                        pass  # Could add logging here if needed

            return total_operations, operation_times

        benchmark.pedantic(endurance_workload, rounds=1, iterations=1)

    def test_endurance_no_auto_tune(self, no_auto_tune_pool, benchmark):
        """Endurance test without auto-tuning (15 seconds)."""
        self._run_endurance_test(no_auto_tune_pool, benchmark, 15.0)

    def test_endurance_with_auto_tune(self, auto_tune_pool, benchmark):
        """Endurance test with auto-tuning (15 seconds)."""
        self._run_endurance_test(auto_tune_pool, benchmark, 15.0)

    def _run_memory_pressure_simulation(self, pool, benchmark, duration_seconds=8.0):
        """Simulate memory pressure scenarios over extended duration."""

        def memory_pressure_workload():
            start_time = time.time()
            held_objects = []
            pressure_cycle = 0

            while time.time() - start_time < duration_seconds:
                pressure_cycle += 1

                if pressure_cycle % 50 == 0:
                    # Simulate memory pressure by holding many objects
                    for _ in range(20):
                        obj_id, key, obj = pool.acquire()
                        held_objects.append((obj_id, key, obj))
                elif pressure_cycle % 25 == 0:
                    # Release half of held objects
                    to_release = held_objects[: len(held_objects) // 2]
                    held_objects = held_objects[len(held_objects) // 2 :]
                    for obj_id, key, obj in to_release:
                        pool.release(obj_id, key, obj)
                else:
                    # Normal operation
                    obj_id, key, obj = pool.acquire()
                    pool.release(obj_id, key, obj)

                time.sleep(0.001)

            # Clean up all held objects
            for obj_id, key, obj in held_objects:
                pool.release(obj_id, key, obj)

        benchmark.pedantic(memory_pressure_workload, rounds=2, iterations=1)

    def test_memory_pressure_no_auto_tune(self, no_auto_tune_pool, benchmark):
        """Memory pressure simulation without auto-tuning (8 seconds)."""
        self._run_memory_pressure_simulation(no_auto_tune_pool, benchmark, 8.0)

    def test_memory_pressure_with_auto_tune(self, auto_tune_pool, benchmark):
        """Memory pressure simulation with auto-tuning (8 seconds)."""
        self._run_memory_pressure_simulation(auto_tune_pool, benchmark, 8.0)
