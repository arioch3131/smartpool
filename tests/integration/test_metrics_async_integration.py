"""
Integration tests for async/sampled metrics modes.
"""

import threading
import time

import pytest

from examples.factories import BytesIOFactory
from smartpool import SmartObjectManager
from smartpool.config import (
    MemoryConfig,
    MetricsMode,
    MetricsOverloadPolicy,
    PoolConfiguration,
)
from smartpool.core.exceptions import PoolAlreadyShutdownError


class TestMetricsAsyncIntegration:
    """Integration coverage for async metrics dispatcher lifecycle."""

    def test_async_mode_concurrent_usage_keeps_pool_operational(self):
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=8,
            ttl_seconds=30.0,
            metrics_mode=MetricsMode.ASYNC,
            metrics_queue_maxsize=256,
            metrics_overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            metrics_flush_timeout_seconds=2.0,
        )
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        errors = []
        num_threads = 6
        loops_per_thread = 40

        def worker() -> None:
            for _ in range(loops_per_thread):
                try:
                    obj_id, key, obj = pool.acquire(initial_size=256)
                    obj.write(b"x")
                    pool.release(obj_id, key, obj)
                except Exception as exc:  # pragma: no cover - defensive in integration loop
                    errors.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors
        assert pool.metrics_dispatcher is not None
        assert pool.metrics_dispatcher.flush(2.0)

        stats = pool.get_basic_stats()
        assert stats["gauges"].get("metrics_worker_alive", 0) >= 0
        assert stats["counters"].get("metrics_events_dropped", 0) >= 0
        pool.shutdown()

    def test_async_mode_shutdown_flushes_and_prevents_new_acquire(self):
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=4,
            ttl_seconds=10.0,
            metrics_mode=MetricsMode.ASYNC,
            metrics_queue_maxsize=32,
            metrics_flush_timeout_seconds=1.0,
            metrics_overload_policy=MetricsOverloadPolicy.DROP_OLDEST,
        )
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        for _ in range(30):
            obj_id, key, obj = pool.acquire(initial_size=128)
            pool.release(obj_id, key, obj)

        assert pool.metrics_dispatcher is not None
        # Let worker process at least part of backlog before shutdown.
        time.sleep(0.05)
        pool.shutdown()
        assert pool.metrics_dispatcher is None

        with pytest.raises(PoolAlreadyShutdownError):
            pool.acquire(initial_size=64)

    def test_async_mode_no_deadlock_under_mixed_lock_pressure(self):
        """
        Stress test lock ordering: pool lock + active/stats/metrics locks.
        The test fails if worker threads do not terminate within timeout.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=6,
            ttl_seconds=20.0,
            metrics_mode=MetricsMode.ASYNC,
            metrics_queue_maxsize=128,
            metrics_overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
            metrics_flush_timeout_seconds=1.0,
        )
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        stop_event = threading.Event()
        errors = []

        def borrow_release_worker() -> None:
            while not stop_event.is_set():
                try:
                    obj_id, key, obj = pool.acquire(initial_size=96)
                    obj.write(b"abc")
                    pool.release(obj_id, key, obj)
                except Exception as exc:  # pragma: no cover
                    errors.append(str(exc))
                    break

        def stats_worker() -> None:
            while not stop_event.is_set():
                try:
                    _ = pool.get_basic_stats()
                    # tiny pause to vary interleavings
                    time.sleep(0.001)
                except Exception as exc:  # pragma: no cover
                    errors.append(str(exc))
                    break

        threads = [threading.Thread(target=borrow_release_worker) for _ in range(4)]
        threads += [threading.Thread(target=stats_worker) for _ in range(2)]

        for thread in threads:
            thread.start()

        time.sleep(0.5)
        stop_event.set()

        for thread in threads:
            thread.join(timeout=2.0)
            assert not thread.is_alive(), "Potential deadlock: thread did not terminate"

        assert not errors
        pool.shutdown()
