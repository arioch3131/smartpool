"""
Basic usage example of the memory pool system with BytesIOFactory.

This file demonstrates how to:
- Initialize a pool with a BytesIO factory
- Acquire and release objects
- Use context managers for automatic management
- Monitor basic statistics
"""

import time

from examples.factories import BytesIOFactory
from smartpool import MemoryConfig, MemoryPreset, SmartObjectManager

# pylint: disable=R0801


# pylint: disable=R0914
def basic_usage_example():
    """Basic usage example of the BytesIO pool."""

    print("=== BytesIO Factory - Basic Usage Example ===\n")

    # 1. Create the factory and the pool
    factory = BytesIOFactory()

    # Custom configuration
    config = MemoryConfig(
        max_objects_per_key=10,  # Max 10 objects per key
        ttl_seconds=300.0,  # Expires after 5 minutes
        enable_logging=True,  # Enable logs to see what's happening
    )

    # Initialize the pool
    pool = SmartObjectManager(factory, default_config=config)

    try:
        # 2. Manual usage (acquire/release)
        print("--- Manual Usage ---")

        # Acquire a 1KB buffer
        obj_id, key, buffer = pool.acquire(1024)  # Initial 1024 bytes
        print(f"Acquired: ID={obj_id}, Key={key}")
        print(f"Buffer size: {len(buffer.getvalue())} bytes")

        # Use the buffer
        buffer.write(b"Hello, World!")
        buffer.seek(0)
        content = buffer.read()
        print(f"Content written: {content}")

        # Release the object
        pool.release(obj_id, key, buffer)
        print("Buffer released and returned to pool")

        # 3. Usage with context manager (recommended)
        print("\n--- Usage with Context Manager ---")

        with pool.acquire_context(2048) as buffer:  # 2KB buffer
            buffer.write(b"Context manager example")
            buffer.seek(0)
            print(f"Content: {buffer.read()}")
            # The buffer will be automatically released when exiting the 'with' block

        # 4. Reuse - demonstrate cache hit
        print("\n--- Reuse Test ---")

        # First acquire - miss (creation)
        obj_id1, key1, buffer1 = pool.acquire(1024)
        print("First acquire - should be a MISS")

        pool.release(obj_id1, key1, buffer1)

        # Second acquire - hit (reuse)
        obj_id2, key2, buffer2 = pool.acquire(1024)
        print("Second acquire - should be a HIT")

        pool.release(obj_id2, key2, buffer2)

        # 5. Statistics
        print("\n--- Statistics ---")
        stats = pool.get_basic_stats()

        print(f"Hits: {stats['counters'].get('hits', 0)}")
        print(f"Misses: {stats['counters'].get('misses', 0)}")
        print(f"Objects created: {stats['counters'].get('creates', 0)}")
        print(f"Reuses: {stats['counters'].get('reuses', 0)}")
        print(f"Objects in pool: {stats.get('total_pooled_objects', 0)}")
        print(f"Active objects: {stats.get('active_objects_count', 0)}")

        # Calculate hit rate
        total_requests = stats["counters"].get("hits", 0) + stats["counters"].get("misses", 0)
        hit_rate = stats["counters"].get("hits", 0) / total_requests if total_requests > 0 else 0
        print(f"Hit rate: {hit_rate:.2%}")

    finally:
        # 6. Cleanup
        pool.shutdown()
        print("\nPool shut down cleanly")


def different_sizes_example():
    """Example showing grouping by size."""
    print("\n=== Example of Grouping by Size ===\n")
    factory = BytesIOFactory()
    pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)
    try:
        # Create buffers of different sizes
        sizes = [512, 1024, 1024, 2048, 2048, 2048, 4096]
        objects = []
        print("Acquiring buffers of different sizes:")
        for size in sizes:
            obj_id, key, buffer = pool.acquire(size)
            objects.append((obj_id, key, buffer))
            print(f"  Size {size}: key = {key}")
        # Release all objects
        for obj_id, key, buffer in objects:
            pool.release(obj_id, key, buffer)
        # See detailed statistics
        detailed_stats = pool.get_detailed_stats()
        print(f"\nNumber of different keys: {len(detailed_stats['by_key'])}")
        for key, stats in detailed_stats["by_key"].items():
            print(f"  {key}: {stats['pooled_count']} objects in pool")
    finally:
        pool.shutdown()


def performance_example():
    """Performance measurement example."""

    print("\n=== Performance Measurement Example ===\n")
    size = 10000
    factory = BytesIOFactory()
    config = MemoryConfig(
        enable_performance_metrics=True,
        enable_acquisition_tracking=True,  # ← Keep but...
        enable_lock_contention_tracking=False,  # ← Remove the most expensive
        max_performance_history_size=50,  # ← Reduce further
    )
    pool = SmartObjectManager(factory, default_config=config)

    try:
        # Perform multiple acquisitions to collect metrics
        print(f"Executing {size} acquisitions/releases...")

        start_time = time.time()

        for i in range(size):
            size_val = 1024 if i % 2 == 0 else 2048  # Alternate sizes

            with pool.acquire_context(size_val) as buffer:
                buffer.write(f"Test {i}".encode())

        end_time = time.time()

        print(f"Total time: {(end_time - start_time) * 1000:.2f}ms")

        # Performance report
        if pool.performance_metrics:
            snapshot = pool.performance_metrics.create_snapshot()

            print("\n--- Performance Metrics ---")
            print(f"Hit rate: {snapshot.hit_rate:.2%}")
            print(f"Average acquisition time: {snapshot.avg_acquisition_time_ms:.2f}ms")
            print(f"P95 acquisition time: {snapshot.p95_acquisition_time_ms:.2f}ms")
            print(f"Throughput: {snapshot.acquisitions_per_second:.1f} ops/sec")

            # Most used keys
            if snapshot.top_keys_by_usage:
                print("\nMost used keys:")
                for key, count in snapshot.top_keys_by_usage[:3]:
                    print(f"  {key}: {count} usages")

    finally:
        pool.shutdown()


if __name__ == "__main__":
    basic_usage_example()
    different_sizes_example()
    performance_example()
