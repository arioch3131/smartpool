"""
Example of using the memory pool for NumPy arrays.

# To run this example, first install the required dependencies:
# pip install -e ".[scientific]"

This file demonstrates how to:
- Manage pools of NumPy arrays for scientific computing.
- Optimize performance for machine learning tasks.
- Handle different shapes and data types.
- Monitor memory usage for large arrays.
"""

import time

import numpy as np

from examples.factories import NumpyArrayFactory
from smartpool import (
    MemoryConfig,
    MemoryPreset,
    MemoryPressure,
    ObjectCreationCost,
    PoolConfiguration,
    SmartObjectManager,
)


def basic_numpy_example():
    """Basic example for NumPy arrays."""
    print("\n=== NumPy Array Pool - Basic Usage ===\n")

    factory = NumpyArrayFactory()

    # Configuration optimized for scientific computing
    config = MemoryConfig(
        max_objects_per_key=15,  # 15 arrays per shape/type
        ttl_seconds=900.0,  # 15 minutes
        enable_logging=True,
        enable_performance_metrics=True,
        object_creation_cost=ObjectCreationCost.MEDIUM,
        memory_pressure=MemoryPressure.NORMAL,
    )
    pool = SmartObjectManager(factory, default_config=config)

    try:
        print("--- Array Creation and Manipulation ---")

        # 1D Array
        with pool.acquire_context((1000,), "float32") as arr1d:
            arr1d[:] = np.random.random(arr1d.shape)
            print(f"1D Array: shape {arr1d.shape}, dtype {arr1d.dtype}")
            print(f"Mean: {np.mean(arr1d):.4f}")

        # 2D Array - matrix
        with pool.acquire_context((100, 100), "float64") as matrix:
            matrix[:] = np.random.random(matrix.shape)
            # Matrix operation
            result = np.dot(matrix, matrix.T)
            print(f"2D Matrix: shape {matrix.shape}")
            print(f"Matrix norm: {np.linalg.norm(result):.4f}")

        # 3D Array - for example, for images
        with pool.acquire_context((64, 64, 3), "uint8") as img_array:
            img_array[:] = np.random.randint(0, 256, img_array.shape, dtype=np.uint8)
            print(
                f"3D Image Array: shape {img_array.shape}, Max value: {np.max(img_array)}"
            )  # Line too long fix

        # Reuse test - same shape and type
        print("\n--- Reuse Test ---")
        with pool.acquire_context((100, 100), "float64") as matrix2:
            # Should reuse the previous array
            print("Acquired a 100x100 float64 matrix (should be a hit)")
            print(f"Initial values (after reset): min={np.min(matrix2)}, max={np.max(matrix2)}")

        # Statistics
        stats = pool.get_basic_stats()
        print("\n--- Statistics ---")
        print(f"Hits: {stats['counters'].get('hits', 0)}")
        print(f"Misses: {stats['counters'].get('misses', 0)}")
        print(f"Arrays created: {stats['counters'].get('total_objects_created', 0)}")
        print(f"Arrays in pool: {stats.get('total_pooled_objects', 0)}")

        # See the different keys generated
        detailed_stats = pool.get_detailed_stats()
        print("\nKeys in pool:")
        for key in detailed_stats.get("by_key", {}):
            print(f"  {key}")

    finally:
        pool.shutdown()


def machine_learning_example():  # pylint: disable=R0914
    """Example of use for machine learning."""
    print("\n=== NumPy Pool for Machine Learning ===\n")

    factory = NumpyArrayFactory()

    # High-performance configuration for ML
    config = MemoryConfig(
        max_objects_per_key=25,
        ttl_seconds=1800.0,  # 30 minutes
        enable_performance_metrics=True,
        max_expected_concurrency=10,
        object_creation_cost=ObjectCreationCost.HIGH,  # Large arrays are expensive
        memory_pressure=MemoryPressure.HIGH,
    )
    pool = SmartObjectManager(factory, default_config=config)

    try:
        print("--- ML Training Simulation ---")

        # Simulated dataset parameters
        n_samples, n_features, n_classes = 100000, 1000, 100
        batch_size, n_epochs = 64, 10

        print(f"Dataset: {n_samples} samples, {n_features} features")
        print(f"Batch size: {batch_size}, Epochs: {n_epochs}")

        start_time = time.time()

        for epoch in range(n_epochs):
            epoch_start = time.time()
            n_batches = n_samples // batch_size

            for _ in range(n_batches):
                # Input data batch
                with pool.acquire_context((batch_size, n_features), "float32"):
                    _ = np.random.random((batch_size, n_features))  # Revert to direct assignment

                    # Labels batch
                    with pool.acquire_context((batch_size,), "int32") as y_batch:
                        y_batch[:] = np.random.randint(0, n_classes, batch_size)

                        # Simulate ML operations
                        # Forward pass simulation
                        with pool.acquire_context(
                            (batch_size, n_classes), "float32"
                        ) as predictions:
                            predictions[:] = np.random.random(predictions.shape)

                            # Loss calculation (simulation)
                            _ = np.mean((predictions - np.eye(n_classes)[y_batch]) ** 2)

                            # Gradients simulation
                            with pool.acquire_context((batch_size, n_features), "float32"):
                                _ = (
                                    np.random.random((batch_size, n_features)) * 0.01
                                )  # Revert to direct assignment

            epoch_time = time.time() - epoch_start
            print(f"  Epoch {epoch + 1}/{n_epochs}: {epoch_time * 1000:.1f}ms")

        total_time = time.time() - start_time
        print(f"\nTotal training time: {total_time:.2f}s")

        if pool.performance_metrics:
            snapshot = pool.performance_metrics.create_snapshot()
            print("\n--- ML Metrics ---")
            print(
                f"Array reuse rate: {snapshot.hit_rate:.2%}, "
                f"Average allocation time: {snapshot.avg_acquisition_time_ms:.2f}ms"
            )  # Line too long fix
            print(
                f"Array throughput: {snapshot.acquisitions_per_second:.1f} arrays/sec"
            )  # Line too long fix

            if snapshot.top_keys_by_usage:
                print("\nMost used shapes:")
                for key, count in snapshot.top_keys_by_usage[:3]:
                    print(f"  {key}: {count} uses")

    finally:
        pool.shutdown()


def scientific_computing_example():
    """Example for intensive scientific calculations."""
    print("\n=== Intensive Scientific Computing ===\n")

    factory = NumpyArrayFactory()
    pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

    try:
        print("--- FFT Calculation Simulation ---")

        signal_length, n_signals = 16384, 10000
        print(f"Processing {n_signals} signals of length {signal_length}")

        start_time = time.time()
        for i in range(n_signals):
            # Original signal
            with pool.acquire_context((signal_length,), "complex128") as signal:
                # Generate a composite signal
                t = np.linspace(0, 1, signal_length)
                signal.real = np.sin(2 * np.pi * 50 * t) + 0.5 * np.sin(2 * np.pi * 120 * t)
                signal.imag = 0
                fft_result = np.fft.fft(signal)

                # Filtered signal
                with pool.acquire_context((signal_length,), "complex128") as filtered:
                    filtered[:] = fft_result
                    filtered[signal_length // 4 : 3 * signal_length // 4] = 0
                    signal_filtered = np.fft.ifft(filtered)
                    if i % 1000 == 0:
                        print(
                            f"  Signal {i + 1}: "
                            f"Original energy={np.sum(np.abs(signal) ** 2):.2f}, "
                            f"Filtered energy={np.sum(np.abs(signal_filtered) ** 2):.2f}"
                        )

        end_time = time.time()
        print(f"\nTotal processing time: {(end_time - start_time) * 1000:.2f}ms")
        print(f"Average time per signal: {((end_time - start_time) * 1000) / n_signals:.2f}ms")
    finally:
        pool.shutdown()


def memory_management_example():
    """Example of memory management for large arrays."""
    print("\n=== Memory Management for Large Arrays ===\n")

    factory = NumpyArrayFactory()
    config = MemoryConfig(
        max_objects_per_key=3,
        ttl_seconds=60.0,
        enable_logging=True,
        memory_pressure=MemoryPressure.HIGH,
    )
    pool_config = PoolConfiguration(max_total_objects=10)
    pool = SmartObjectManager(factory, default_config=config, pool_config=pool_config)

    try:
        print("--- Testing with different array sizes ---")
        shapes = [(1000,), (1000, 1000), (100, 100, 100), (2000, 2000)]

        for i, shape in enumerate(shapes):
            with pool.acquire_context(shape, "float64") as arr:
                size_mb = arr.nbytes / (1024 * 1024)
                print(f"  Array {i + 1}: shape {shape}, size {size_mb:.1f} MB")
                arr.fill(i + 1)
                checksum = np.sum(arr)
                print(f"    Checksum: {checksum:.2e}")

        detailed_stats = pool.get_detailed_stats()
        total_memory_mb = detailed_stats.get("total_memory_bytes", 0) / (1024 * 1024)

        print("\n--- Memory Usage ---")
        print(f"Total pool memory: {total_memory_mb:.1f} MB")
        for key, stats in detailed_stats.get("by_key", {}).items():
            key_memory_mb = stats["memory_bytes"] / (1024 * 1024)
            print(f"  {key}: {stats['pooled_count']} arrays, {key_memory_mb:.1f} MB")

    finally:
        pool.shutdown()


def multiple_dtypes_example():
    """Example with different NumPy data types."""
    print("\n=== Multiple Data Types ===\n")

    factory = NumpyArrayFactory()
    pool = SmartObjectManager(factory)

    dtypes_to_test = [
        ("int32", "32-bit Integers"),
        ("float32", "32-bit Floats"),
        ("float64", "64-bit Floats"),
        ("complex128", "128-bit Complex"),
        ("bool", "Booleans"),
        ("int32", "32-bit Integers (bis)"),
    ]

    try:
        print("--- Testing with different dtypes ---")
        for dtype, description in dtypes_to_test:
            with pool.acquire_context((100, 100), dtype) as arr:
                if dtype == "bool":
                    arr[:] = np.random.random(arr.shape) > 0.5
                    result = f"Number of True: {np.sum(arr)}"
                elif "complex" in dtype:
                    arr.real = np.random.random((100, 100))
                    arr.imag = np.random.random((100, 100))
                    result = f"Average modulus: {np.mean(np.abs(arr)):.4f}"
                else:
                    arr[:] = np.random.random(arr.shape).astype(dtype)
                    result = f"Average: {np.mean(arr):.4f}"
                print(f"  {dtype} ({description}): {result}")

        detailed_stats = pool.get_detailed_stats()
        print("\nGenerated keys:")
        for key in sorted(detailed_stats.get("by_key", {}).keys()):
            count = detailed_stats["by_key"][key]["pooled_count"]
            print(f"  {key}: {count} arrays")

    finally:
        pool.shutdown()


if __name__ == "__main__":
    basic_numpy_example()
    machine_learning_example()
    scientific_computing_example()
    memory_management_example()
    multiple_dtypes_example()
