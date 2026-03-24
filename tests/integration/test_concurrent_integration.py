"""
Integration tests for SmartObjectManager concurrent access and threading.
These tests ensure thread safety and proper behavior under concurrent load.
"""

import random
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from examples.factories import BytesIOFactory, MetadataFactory
from smartpool import SmartObjectManager
from smartpool.config import MemoryConfig, PoolConfiguration


class TestConcurrentIntegration:
    """
    Integration tests for SmartObjectManager concurrent access scenarios.
    """

    def test_concurrent_acquire_release(self):
        """
        Test concurrent acquire and release operations from multiple threads.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(max_objects_per_key=10, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        results = {}
        num_threads = 8
        operations_per_thread = 50

        def worker_function(thread_id):
            """Worker function for each thread."""
            operations = []
            errors = []

            for i in range(operations_per_thread):
                try:
                    # Acquire object
                    start_time = time.time()
                    obj_id, key, obj = pool.acquire()
                    acquire_time = time.time() - start_time

                    # Use object briefly
                    obj.write(f"Thread {thread_id}, Operation {i}".encode())
                    content = obj.getvalue()
                    assert len(content) > 0

                    # Small random delay to simulate work
                    time.sleep(random.uniform(0.001, 0.005))

                    # Release object
                    start_time = time.time()
                    pool.release(obj_id, key, obj)
                    release_time = time.time() - start_time

                    operations.append(
                        {
                            "acquire_time": acquire_time,
                            "release_time": release_time,
                            "content_length": len(content),
                        }
                    )

                except Exception as e:
                    errors.append(str(e))

            results[thread_id] = {"operations": operations, "errors": errors}

        try:
            # Start all threads
            threads = []
            for i in range(num_threads):
                thread = threading.Thread(target=worker_function, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Verify results
            total_operations = 0
            total_errors = 0

            for thread_id, result in results.items():
                total_operations += len(result["operations"])
                total_errors += len(result["errors"])

                # Verify no errors in this thread
                assert len(result["errors"]) == 0, (
                    f"Thread {thread_id} had errors: {result['errors']}"
                )

                # Verify expected number of operations
                assert len(result["operations"]) == operations_per_thread

            # Verify total operations
            assert total_operations == num_threads * operations_per_thread
            assert total_errors == 0

            # Verify pool statistics
            stats = pool.get_basic_stats()
            assert stats["counters"]["creates"] > 0
            assert stats["counters"]["hits"] + stats["counters"]["misses"] == total_operations

        finally:
            pool.shutdown()

    def test_concurrent_pool_exhaustion_and_recovery(self):
        """
        Test behavior when pool is exhausted by concurrent threads.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(max_objects_per_key=5, ttl_seconds=60)  # Small pool
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        num_threads = 15  # More threads than pool capacity
        operations_per_thread = 10
        results = {}

        def worker_function(thread_id):
            """Worker function that holds objects for varying durations."""
            held_objects = []
            operations = 0

            try:
                for i in range(operations_per_thread):
                    # Acquire object
                    obj_id, key, obj = pool.acquire()
                    held_objects.append((obj_id, key, obj))
                    operations += 1

                    # Hold object for random duration
                    hold_time = random.uniform(0.01, 0.05)
                    time.sleep(hold_time)

                    # Release half the objects randomly
                    if len(held_objects) > 2 and random.random() < 0.5:
                        obj_to_release = held_objects.pop(random.randint(0, len(held_objects) - 1))
                        pool.release(*obj_to_release)

                # Release all remaining objects
                for obj_id, key, obj in held_objects:
                    pool.release(obj_id, key, obj)

            except Exception as e:
                # Release any held objects in case of error
                for obj_id, key, obj in held_objects:
                    try:
                        pool.release(obj_id, key, obj)
                    except Exception:
                        pass
                raise e

            results[thread_id] = {"operations": operations}

        try:
            # Start all threads
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(worker_function, i) for i in range(num_threads)]

                # Wait for all threads to complete
                for future in as_completed(futures):
                    future.result()  # This will raise any exceptions

            # Verify all threads completed successfully
            assert len(results) == num_threads

            # Verify pool is in clean state
            stats = pool.get_basic_stats()
            assert stats["active_objects_count"] == 0
            assert stats["counters"]["creates"] >= config.max_objects_per_key

        finally:
            pool.shutdown()

    def test_concurrent_shutdown_safety(self):
        """
        Test that shutdown is safe even when threads are actively using the pool.
        """
        factory = MetadataFactory()
        config = MemoryConfig(max_objects_per_key=5, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        shutdown_initiated = threading.Event()
        results = defaultdict(list)
        errors = defaultdict(list)

        def worker_function(thread_id):
            """Worker that continues until shutdown is initiated."""
            operation_count = 0

            while not shutdown_initiated.is_set():
                try:
                    # Try to acquire object
                    obj_id, key, obj = pool.acquire()
                    obj[f"thread_{thread_id}"] = operation_count

                    # Small delay
                    time.sleep(0.001)

                    # Release object
                    pool.release(obj_id, key, obj)
                    operation_count += 1

                    # Break if too many operations (safety limit)
                    if operation_count > 100:
                        break

                except Exception as e:
                    errors[thread_id].append(str(e))
                    # If we get shutdown error, that's expected
                    if "shutdown" in str(e).lower():
                        break

            results[thread_id] = operation_count

        try:
            # Start worker threads
            threads = []
            num_threads = 5

            for i in range(num_threads):
                thread = threading.Thread(target=worker_function, args=(i,))
                threads.append(thread)
                thread.start()

            # Let threads work for a short time
            time.sleep(0.1)

            # Initiate shutdown
            shutdown_initiated.set()
            pool.shutdown()

            # Wait for threads to finish
            for thread in threads:
                thread.join(timeout=2.0)  # Don't wait forever

            # Verify results
            assert len(results) >= 1  # At least one thread should have done work

            # Errors should only be shutdown-related
            for thread_id, thread_errors in errors.items():
                for error in thread_errors:
                    assert "shutdown" in error.lower() or "pool" in error.lower()

        finally:
            # Ensure pool is shutdown
            try:
                pool.shutdown()
            except Exception:
                pass

    def test_concurrent_background_cleanup(self):
        """
        Test that background cleanup works correctly with concurrent access.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=8,
            ttl_seconds=0.1,  # Very short TTL
            cleanup_interval_seconds=0.05,  # Frequent cleanup
        )
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        # Start background cleanup
        pool.background_manager.start_background_cleanup()

        results = {}
        num_threads = 4
        operations_per_thread = 20

        def worker_function(thread_id):
            """Worker that creates objects that will expire."""
            operations = 0
            for i in range(operations_per_thread):
                try:
                    # Acquire and immediately release to create pooled objects
                    obj_id, key, obj = pool.acquire()
                    obj.write(f"Thread {thread_id} data".encode())
                    pool.release(obj_id, key, obj)
                    operations += 1

                    # Small delay to let objects accumulate and expire
                    time.sleep(0.02)

                except Exception:
                    break  # Stop on any error

            results[thread_id] = operations

        try:
            # Start worker threads
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(worker_function, i) for i in range(num_threads)]

                # Wait for completion
                for future in as_completed(futures):
                    future.result()

            # Allow some time for final cleanup
            time.sleep(0.2)

            # Verify that cleanup occurred (objects should be removed due to TTL)
            stats = pool.get_basic_stats()

            # Due to TTL and cleanup, fewer objects should remain than created
            total_operations = sum(results.values())
            assert total_operations > 0

            # Background cleanup should have removed expired objects
            assert stats["total_pooled_objects"] < total_operations

        finally:
            pool.shutdown()

    def test_concurrent_statistics_accuracy(self):
        """
        Test that statistics remain accurate under concurrent access.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(max_objects_per_key=10, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        num_threads = 6
        operations_per_thread = 30
        results = {}

        def worker_function(thread_id):
            """Worker that tracks its own operations."""
            local_acquires = 0
            local_releases = 0

            for i in range(operations_per_thread):
                try:
                    obj_id, key, obj = pool.acquire()
                    local_acquires += 1

                    # Use object
                    obj.write(f"Thread {thread_id} op {i}".encode())

                    # Small delay
                    time.sleep(0.001)

                    pool.release(obj_id, key, obj)
                    local_releases += 1

                except Exception:
                    break

            results[thread_id] = {"acquires": local_acquires, "releases": local_releases}

        try:
            # Execute concurrent operations
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(worker_function, i) for i in range(num_threads)]

                for future in as_completed(futures):
                    future.result()

            # Calculate expected totals
            total_expected_ops = sum(r["acquires"] for r in results.values())

            # Get pool statistics
            stats = pool.get_basic_stats()

            # Verify statistics accuracy
            total_pool_ops = stats["counters"]["hits"] + stats["counters"]["misses"]
            assert total_pool_ops == total_expected_ops

            # Verify no objects are left active
            assert stats["active_objects_count"] == 0

            # Verify all threads completed expected operations
            for thread_id, result in results.items():
                assert result["acquires"] == operations_per_thread
                assert result["releases"] == operations_per_thread

        finally:
            pool.shutdown()

    def test_concurrent_memory_pressure_handling(self):
        """
        Test pool behavior under concurrent memory pressure scenarios.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(max_objects_per_key=3, ttl_seconds=60)  # Very small pool
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        num_threads = 10  # High pressure
        results = {}

        def high_pressure_worker(thread_id):
            """Worker that creates high memory pressure."""
            operations = 0
            max_held = 0
            held_objects = []

            try:
                for i in range(20):
                    # Acquire objects
                    obj_id, key, obj = pool.acquire()
                    held_objects.append((obj_id, key, obj))
                    operations += 1

                    # Track maximum held
                    max_held = max(max_held, len(held_objects))

                    # Occasionally release some objects
                    if len(held_objects) > 5 or (i > 0 and i % 7 == 0):
                        for _ in range(min(3, len(held_objects))):
                            if held_objects:
                                obj_to_release = held_objects.pop(0)
                                pool.release(*obj_to_release)

                    time.sleep(0.002)

                # Release all remaining objects
                for obj_id, key, obj in held_objects:
                    pool.release(obj_id, key, obj)

            except Exception:
                # Clean up on error
                for obj_id, key, obj in held_objects:
                    try:
                        pool.release(obj_id, key, obj)
                    except Exception:
                        pass

            results[thread_id] = {"operations": operations, "max_held": max_held}

        try:
            # Run high-pressure concurrent test
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(high_pressure_worker, i) for i in range(num_threads)]

                for future in as_completed(futures):
                    future.result()

            # Verify all threads completed successfully
            assert len(results) == num_threads

            # Verify pool handled pressure correctly
            stats = pool.get_basic_stats()
            assert stats["active_objects_count"] == 0
            assert (
                stats["counters"]["creates"] > config.max_objects_per_key
            )  # Should have created extra

            # Verify operations completed
            total_operations = sum(r["operations"] for r in results.values())
            assert total_operations > 0

        finally:
            pool.shutdown()
