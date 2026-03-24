"""
Example of using the memory pool for PIL images.

# To run this example, first install the required dependencies:
# pip install -e ".[imaging]"

This file demonstrates how to:
- Manage pools of images of different sizes and formats
- Optimize reuse for batch image processing
- Monitor memory usage
- Apply image processing operations
"""

import time

from PIL import ImageDraw, ImageFilter

from examples.factories import PILImageFactory
from smartpool import MemoryConfig, MemoryPreset, MemoryPressure, SmartObjectManager


def basic_image_processing_example():
    """Basic example for image processing."""

    print("=== PIL Image Pool - Basic Processing ===\n")

    # Optimized configuration for images
    factory = PILImageFactory(enable_reset=True)
    config = MemoryConfig(
        max_objects_per_key=20,  # Keep up to 20 images of each size
        ttl_seconds=600.0,  # 10 minutes lifetime
        enable_logging=True,
        enable_performance_metrics=True,
    )

    pool = SmartObjectManager(factory, default_config=config)

    try:
        print("--- Image Creation and Manipulation ---")

        # Create an image and draw on it
        with pool.acquire_context(800, 600, "RGB") as img:
            # Draw something on the image
            draw = ImageDraw.Draw(img)
            draw.rectangle([100, 100, 700, 500], fill="lightblue", outline="navy", width=3)
            draw.text((400, 300), "Hello PIL Pool!", fill="darkblue")

            print(f"Image created: {img.size}, mode: {img.mode}")

            # Apply a filter
            _ = img.filter(ImageFilter.BLUR)
            print("Blur filter applied")

        # Test with different sizes to see grouping
        test_sizes = [
            (640, 480),  # VGA
            (800, 600),  # SVGA
            (1024, 768),  # XGA
            (800, 600),  # SVGA again (should be a hit)
            (640, 480),  # VGA again (should be a hit)
        ]

        print(f"\n--- Reuse Test with {len(test_sizes)} images ---")

        for i, (w, h) in enumerate(test_sizes):
            with pool.acquire_context(w, h, "RGB") as img:
                # Simulate processing
                draw = ImageDraw.Draw(img)
                draw.ellipse([50, 50, w - 50, h - 50], fill="red", outline="black")
                print(f"Image {i + 1}: {w}x{h} processed")

        # Statistics
        stats = pool.get_basic_stats()
        print("\n--- Statistics ---")
        print(f"Hits: {stats['counters'].get('hits', 0)}")
        print(f"Misses: {stats['counters'].get('misses', 0)}")
        print(f"Images in pool: {stats.get('total_pooled_objects', 0)}")

    finally:
        pool.shutdown()


def batch_processing_example():
    """Example of batch image processing."""

    print("\n=== Batch Image Processing ===\n")

    factory = PILImageFactory()
    pool = SmartObjectManager(factory, preset=MemoryPreset.IMAGE_PROCESSING)

    try:
        # Simulate processing a batch of images of the same size
        standard_size = (1024, 768)
        num_images = 50

        print(f"Processing {num_images} images of size {standard_size}")

        start_time = time.time()

        for i in range(num_images):
            with pool.acquire_context(*standard_size, "RGB") as img:
                # Simulate different treatments depending on the image
                draw = ImageDraw.Draw(img)

                if i % 3 == 0:
                    # Draw a rectangle
                    draw.rectangle([0, 0, 200, 200], fill=f"hsl({i * 7 % 360}, 50%, 50%)")
                elif i % 3 == 1:
                    # Draw a circle
                    draw.ellipse([0, 0, 200, 200], fill=f"hsl({i * 7 % 360}, 70%, 60%)")
                else:
                    # Apply a filter
                    img.paste(img.filter(ImageFilter.EDGE_ENHANCE))

        end_time = time.time()

        print(f"Processing time: {(end_time - start_time) * 1000:.2f}ms")
        print(f"Average time per image: {((end_time - start_time) * 1000) / num_images:.2f}ms")

        # Detailed metrics
        if pool.performance_metrics:
            snapshot = pool.performance_metrics.create_snapshot()
            print(f"\nReuse rate: {snapshot.hit_rate:.2%}")
            print(f"Average acquisition time: {snapshot.avg_acquisition_time_ms:.2f}ms")

    finally:
        pool.shutdown()


def multiple_formats_example():
    """Example with different image formats."""

    print("\n=== Handling Multiple Formats ===\n")

    factory = PILImageFactory()
    pool = SmartObjectManager(factory)

    formats_test = [
        ("RGB", "Red-Green-Blue"),
        ("RGBA", "Red-Green-Blue-Alpha"),
        ("L", "Grayscale"),
        ("RGB", "RGB again"),  # Should reuse
    ]

    try:
        print("Testing with different formats:")

        for mode, description in formats_test:
            with pool.acquire_context(512, 512, mode) as img:
                draw = ImageDraw.Draw(img)

                if mode == "RGB":
                    draw.rectangle([100, 100, 400, 400], fill="red")
                elif mode == "RGBA":
                    draw.rectangle([100, 100, 400, 400], fill=(0, 255, 0, 128))
                elif mode == "L":
                    draw.rectangle([100, 100, 400, 400], fill=128)

                print(f"  {mode} ({description}): {img.size}")

        # See the different keys generated
        detailed_stats = pool.get_detailed_stats()
        print("\nKeys generated in the pool:")
        for key in detailed_stats["by_key"]:
            print(f"  {key}")

    finally:
        pool.shutdown()


def memory_monitoring_example():
    """Example of memory usage monitoring."""

    print("\n=== Memory Monitoring ===\n")

    factory = PILImageFactory()

    # Configuration with strict memory limits
    config = MemoryConfig(
        max_objects_per_key=5,  # Only 5 images per size
        ttl_seconds=30.0,  # Fast expiration
        enable_performance_metrics=True,
        memory_pressure=MemoryPressure.HIGH,  # Indicate high memory pressure
    )

    pool = SmartObjectManager(factory, default_config=config)

    try:
        # Create increasingly larger images
        sizes = [(200, 200), (400, 400), (800, 800), (1600, 1600)]

        print("Creating images of increasing sizes:")

        for w, h in sizes:
            with pool.acquire_context(w, h, "RGB"):
                # Calculate approximate size
                estimated_size = w * h * 3  # 3 bytes per pixel for RGB
                print(f"  {w}x{h}: ~{estimated_size / 1024:.1f} KB")

        # Detailed memory statistics
        detailed_stats = pool.get_detailed_stats()
        total_memory = detailed_stats.get("total_memory_bytes", 0)

        print(f"\nTotal memory usage: {total_memory / 1024:.1f} KB")

        print("\nBy key:")
        for key, stats in detailed_stats["by_key"].items():
            memory_kb = stats["memory_bytes"] / 1024
            print(f"  {key}: {stats['pooled_count']} images, {memory_kb:.1f} KB")

    finally:
        pool.shutdown()


def automatic_optimization_example():
    """Example of automatic optimization."""

    print("\n=== Automatic Optimization ===\n")

    factory = PILImageFactory()
    pool = SmartObjectManager(factory, preset=MemoryPreset.IMAGE_PROCESSING)

    try:
        # Enable auto-tuning
        pool.enable_auto_tuning(interval_seconds=10.0)  # Very short for demo

        print("Auto-tuning enabled")

        # Simulate a workload that could benefit from optimization
        print("Simulating a workload...")

        # Phase 1: Many misses (bad hit rate)
        for i in range(30):
            # Slightly different sizes to force misses
            w, h = 500 + (i % 5), 500 + (i % 5)
            with pool.acquire_context(w, h, "RGB"):
                pass

        time.sleep(1)  # Allow metrics to update

        # Get optimization recommendations
        recommendations = pool.manager.get_optimization_recommendations()

        print("\n--- Optimization Recommendations ---")
        print(f"Urgency level: {recommendations.get('urgency_level', 'unknown')}")

        for rec in recommendations.get("recommendations", []):
            print(f"  {rec['type'].upper()}: {rec['reason']}")
            print(f"    {rec['parameter']}: {rec['current']} -> {rec['recommended']}")

    finally:
        pool.shutdown()


if __name__ == "__main__":
    basic_image_processing_example()
    batch_processing_example()
    multiple_formats_example()
    memory_monitoring_example()
    automatic_optimization_example()
