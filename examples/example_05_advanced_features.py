"""
Example of advanced features of the memory pool system.

This file shows how to:
- Use configuration presets
- Enable and configure automatic optimization
- Monitor performance in real-time
- Generate detailed reports
- Manage alerts and recommendations
- Configure monitoring and metrics
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from examples.factories import BytesIOFactory
from smartpool import (
    MemoryConfig,
    MemoryPreset,
    MemoryPressure,
    ObjectCreationCost,
    PoolConfiguration,
    SmartObjectManager,
)


def example_presets_configuration():
    """Example of using configuration presets."""

    print("=== Configuration Presets ===\n")

    factory = BytesIOFactory()

    # Test different presets
    presets_to_test = [
        MemoryPreset.LOW_MEMORY,
        MemoryPreset.HIGH_THROUGHPUT,
        MemoryPreset.IMAGE_PROCESSING,
        MemoryPreset.DATABASE_CONNECTIONS,
        MemoryPreset.DEVELOPMENT,
    ]

    for preset in presets_to_test:
        print(f"--- Preset: {preset.value} ---")

        pool = SmartObjectManager(factory, preset=preset)

        try:
            # Get preset information
            preset_info = pool.get_preset_info()
            print(f"Description: {preset_info['description']}")

            config = pool.default_config
            print("Configuration:")
            print(f"  - Max size: {config.max_objects_per_key}")
            print(f"  - TTL: {config.ttl_seconds}s")
            print(f"  - Cleanup interval: {config.cleanup_interval_seconds}s")
            print(f"  - Performance metrics: {config.enable_performance_metrics}")
            print(f"  - Expected concurrency: {config.max_expected_concurrency}")
            print(f"  - Object creation cost: {config.object_creation_cost}")
            print(f"  - Memory pressure: {config.memory_pressure}")

            # Quick test with the preset
            start_time = time.time()
            for i in range(20):
                with pool.acquire_context(1024) as buffer:
                    buffer.write(f"Test {i}".encode())

            test_time = (time.time() - start_time) * 1000
            stats = pool.get_basic_stats()
            hit_rate = stats["counters"].get("hits", 0) / (
                stats["counters"].get("hits", 0) + stats["counters"].get("misses", 0)
            )

            print(f"Test (20 operations): {test_time:.2f}ms, Hit rate: {hit_rate:.2%}")

        finally:
            pool.shutdown()

        print()


# pylint: disable=R0914
def example_automatic_optimization():
    """Example of advanced automatic optimization."""

    print("=== Automatic Optimization ===\n")

    factory = BytesIOFactory()

    # Configuration with optimization
    config = MemoryConfig(
        max_objects_per_key=10,  # Intentionally small to trigger optimization
        ttl_seconds=30.0,  # Short TTL
        enable_performance_metrics=True,
        enable_acquisition_tracking=True,
        enable_lock_contention_tracking=True,
        max_performance_history_size=200,
    )

    pool = SmartObjectManager(factory, default_config=config)

    try:
        # Enable auto-tuning with a short interval for the demo
        pool.enable_auto_tuning(interval_seconds=3.0)

        print("--- Phase 1: Normal load ---")

        # Generate a load that will show performance problems
        for i in range(30):
            with pool.acquire_context(1024) as buffer:
                buffer.write(f"Normal load {i}".encode())
                time.sleep(0.01)  # Small pause

        # First analysis
        analysis1 = pool.manager.get_optimization_recommendations()
        print("First recommendations:")
        print(f"  Urgency: {analysis1['urgency_level']}")
        print(f"  Score: {analysis1['urgency_score']}")

        for rec in analysis1["recommendations"][:2]:  # First 2 recommendations
            print(f"  - {rec['type'].upper()}: {rec['reason']}")

        print("\n--- Phase 2: Intensive load ---")

        # Generate a more intensive load to force optimization
        start_time = time.time()

        for i in range(100):
            # Vary sizes to create more misses
            size = 1024 if i % 3 == 0 else 2048
            with pool.acquire_context(size) as buffer:
                buffer.write(f"Intensive load {i}".encode())

        intensive_time = time.time() - start_time

        # Allow time for auto-tuning to run
        time.sleep(4.0)

        # Analysis after optimization
        _ = pool.manager.get_optimization_recommendations()
        tuning_info = pool.optimizer.get_tuning_info()

        print(f"Intensive load time: {intensive_time * 1000:.2f}ms")
        print(f"Auto-tuning enabled: {tuning_info['enabled']}")
        print(f"Adjustments made: {tuning_info['adjustments_count']}")

        if tuning_info["history"]:
            last_adjustment = tuning_info["history"][-1]
            print("Last adjustment:")
            for param, change in last_adjustment["adjustments"].items():
                print(f"  {param}: {change['from']} -> {change['to']}")

        print("\n--- Phase 3: Post-optimization test ---")

        # Test after optimization
        start_time = time.time()

        for i in range(50):
            with pool.acquire_context(1024) as buffer:
                buffer.write(f"Post-optimization {i}".encode())

        post_opt_time = time.time() - start_time

        print(f"Post-optimization time: {post_opt_time * 1000:.2f}ms")

        # Performance comparison
        if pool.performance_metrics:
            perf_report = pool.get_performance_report(detailed=True)
            current_metrics = perf_report["performance"]["current_metrics"]

            print("\n--- Final Metrics ---")
            print(f"Hit rate: {current_metrics['hit_rate']:.2%}")
            print(f"Average time: {current_metrics['avg_acquisition_time_ms']:.2f}ms")
            print(f"Throughput: {current_metrics['acquisitions_per_second']:.1f} ops/sec")

    finally:
        pool.shutdown()


# pylint: disable=R0914
def example_real_time_monitoring():  # noqa: PLR0915
    """Example of real-time monitoring."""

    print("\n=== Real-time Monitoring ===\n")

    factory = BytesIOFactory()

    config = MemoryConfig(
        max_objects_per_key=15,
        enable_performance_metrics=True,
        enable_acquisition_tracking=True,
        max_performance_history_size=500,
    )

    pool = SmartObjectManager(factory, default_config=config)

    def worker_function(worker_id, n_operations):
        """Worker function to simulate concurrent load."""
        for i in range(n_operations):
            size = 1024 + (worker_id * 512)  # Different sizes per worker
            with pool.acquire_context(size) as buffer:
                buffer.write(f"Worker {worker_id} operation {i}".encode())
                # Simulate variable processing
                time.sleep(0.001 + (worker_id * 0.0005))

    try:
        print("--- Starting concurrent monitoring ---")

        # Start several workers in parallel
        n_workers = 5
        operations_per_worker = 20

        print(f"Launching {n_workers} workers with {operations_per_worker} operations each")

        start_time = time.time()

        # Real-time monitoring in a separate thread
        monitoring_active = True

        def monitor_loop():
            """Monitoring loop."""
            while monitoring_active:
                if pool.performance_metrics:
                    snapshot = pool.performance_metrics.create_snapshot()
                    stats = pool.get_basic_stats()

                    print(
                        f"  [Monitor] Active: {stats.get('active_objects_count', 0)}, "
                        f"Pooled: {stats.get('total_pooled_objects', 0)}, "
                        f"Hit rate: {snapshot.hit_rate:.1%}, "
                        f"Avg time: {snapshot.avg_acquisition_time_ms:.1f}ms"
                    )

                time.sleep(1.0)

        # Start monitoring
        monitor_thread = threading.Thread(target=monitor_loop)
        monitor_thread.start()

        # Execute workers
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = []
            for worker_id in range(n_workers):
                future = executor.submit(worker_function, worker_id, operations_per_worker)
                futures.append(future)

            # Wait for all workers to finish
            for future in futures:
                future.result()

        # Stop monitoring
        monitoring_active = False
        monitor_thread.join()

        end_time = time.time()

        print("\n--- Concurrent Test Results ---")
        print(f"Total time: {(end_time - start_time) * 1000:.2f}ms")
        print(f"Total operations: {n_workers * operations_per_worker}")

        # Final detailed report
        if pool.performance_metrics:
            final_report = pool.get_performance_report(detailed=True)

            current = final_report["performance"]["current_metrics"]
            print(f"Final hit rate: {current['hit_rate']:.2%}")
            print(f"Peak concurrency: {current['peak_concurrent_acquisitions']}")
            print(f"Lock contention: {current['lock_contention_rate']:.1%}")

            # Statistics by key
            key_stats = final_report["key_statistics"]
            if key_stats:
                print("\nStatistics by object type:")
                for key, stats in key_stats.items():
                    print(
                        f"  {key}: {stats['usage_count']} uses, "
                        f"{stats['avg_time_ms']:.1f}ms avg, "
                        f"{stats['hit_rate']:.1%} hit rate"
                    )

    finally:
        pool.shutdown()


# pylint: disable=R0914,R0912,R0915
def example_detailed_reports():  # noqa: PLR0912,PLR0915
    """Example of generating detailed reports."""

    print("\n=== Detailed Reports ===\n")

    factory = BytesIOFactory()
    pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

    try:
        # Generate varied workload for interesting data
        print("--- Generating test data ---")

        # Phase 1: Light load
        for i in range(20):
            with pool.acquire_context(1024) as buffer:
                buffer.write(f"Light load {i}".encode())

        # Phase 2: Variable load
        for i in range(30):
            size = [512, 1024, 2048, 4096][i % 4]
            with pool.acquire_context(size) as buffer:
                buffer.write(f"Variable load {i}".encode())

        # Phase 3: Intensive load
        start_intensive = time.time()
        for i in range(50):
            with pool.acquire_context(1024) as buffer:
                buffer.write(f"Intensive load {i}".encode())
                if i % 10 == 0:
                    time.sleep(0.01)  # Occasional pause
        end_intensive = time.time()

        print(f"Data generated in {(end_intensive - start_intensive) * 1000:.2f}ms")

        # Full performance report
        print("\n--- Full Performance Report ---")

        perf_report = pool.get_performance_report(detailed=True)

        # Basic metrics
        basic_stats = perf_report["basic_stats"]
        print("Basic statistics:")
        print(f"  Hits: {basic_stats['counters'].get('hits', 0)}")
        print(f"  Misses: {basic_stats['counters'].get('misses', 0)}")
        print(f"  Creates: {basic_stats['counters'].get('creates', 0)}")
        print(f"  Reuses: {basic_stats['counters'].get('reuses', 0)}")

        # Current configuration
        config_info = perf_report["config"]
        print("\nConfiguration:")
        print(f"  Max size: {config_info['max_objects_per_key']}")
        print(f"  TTL: {config_info['ttl_seconds']}s")
        print(f"  Expected concurrency: {config_info['max_expected_concurrency']}")

        # Advanced performance metrics
        if "performance" in perf_report:
            current_metrics = perf_report["performance"]["current_metrics"]
            print("\nPerformance Metrics:")
            print(f"  Hit rate: {current_metrics['hit_rate']:.2%}")
            print(f"  Average time: {current_metrics['avg_acquisition_time_ms']:.2f}ms")
            print(f"  P95: {current_metrics['p95_acquisition_time_ms']:.2f}ms")
            print(f"  P99: {current_metrics['p99_acquisition_time_ms']:.2f}ms")
            print(f"  Throughput: {current_metrics['acquisitions_per_second']:.1f} ops/sec")

            # Alerts
            alerts = perf_report["performance"]["alerts"]
            if alerts:
                print(f"\nAlerts ({len(alerts)}):")
                for alert in alerts:
                    print(f"  {alert['level'].upper()}: {alert['message']}")

            # Recommendations
            recommendations = perf_report["performance"]["recommendations"]
            if recommendations:
                print("\nRecommendations:")
                for rec in recommendations:
                    print(f"  - {rec}")

        # Detailed statistics by key
        detailed_stats = pool.get_detailed_stats()
        print("\n--- Detailed Statistics ---")
        print(f"Total memory: {detailed_stats.get('total_memory_bytes', 0) / 1024:.1f} KB")

        for key, key_stats in detailed_stats["by_key"].items():
            print(f"\nKey: {key}")
            print(f"  Objects in pool: {key_stats['pooled_count']}")
            print(f"  Active objects: {key_stats['active_count']}")
            print(f"  Memory: {key_stats['memory_bytes'] / 1024:.1f} KB")
            print(f"  Max size config: {key_stats['config']['max_objects_per_key']}")
            print(
                f"  Last used: {time.time() - key_stats.get('last_access', time.time()):.1f}s ago"
            )

        # Health status
        health_status = pool.get_health_status()
        print("\n--- Health Status ---")
        print(f"Overall status: {health_status['status'].upper()}")
        print(f"Hit rate: {health_status['hit_rate']:.2%}")
        print(f"Corruption rate: {health_status['corruption_rate']:.2%}")

        if health_status["issues"]:
            print("Issues detected:")
            for issue in health_status["issues"]:
                print(f"  - {issue}")
        else:
            print("No issues detected")

        # Dashboard summary
        dashboard = pool.manager.get_dashboard_summary()
        print("\n--- Dashboard Summary ---")
        print(f"Status: {dashboard['status']}")
        print(f"Preset: {dashboard['preset']}")
        print(
            f"Key metrics: Hit rate {dashboard['metrics']['hit_rate']:.1%}, "
            f"{dashboard['metrics']['total_pooled_objects']} pooled, "
            f"{dashboard['metrics']['active_objects_count']} active"
        )

        if "alerts" in dashboard:
            print(f"Alerts: {dashboard.get('alerts', 0)}, Warnings: {dashboard.get('warnings', 0)}")

    finally:
        pool.shutdown()


def example_custom_configuration():
    """Example of advanced custom configuration."""

    print("\n=== Custom Configuration ===\n")

    factory = BytesIOFactory()

    # Sophisticated custom configuration
    custom_config = MemoryConfig(
        max_objects_per_key=30,
        ttl_seconds=1200.0,  # 20 minutes
        cleanup_interval_seconds=180.0,  # Cleanup every 3 minutes
        enable_logging=True,
        enable_background_cleanup=True,
        max_validation_attempts=2,
        max_corrupted_objects=8,
        # Performance metrics
        enable_performance_metrics=True,
        enable_acquisition_tracking=True,
        enable_lock_contention_tracking=True,
        max_performance_history_size=1000,
        # Usage parameters
        max_expected_concurrency=25,
        object_creation_cost=ObjectCreationCost.MEDIUM,
        memory_pressure=MemoryPressure.NORMAL,
    )

    pool_config = PoolConfiguration(
        max_total_objects=100, enable_monitoring=True, register_atexit=True
    )
    pool = SmartObjectManager(factory, default_config=custom_config, pool_config=pool_config)

    try:
        print("--- Custom configuration applied ---")

        # Display configuration
        config = pool.default_config
        print("Configuration:")
        print(f"  Max size: {config.max_objects_per_key}")
        print(f"  TTL: {config.ttl_seconds}s")
        print(f"  Cleanup interval: {config.cleanup_interval_seconds}s")
        print(f"  Max validation attempts: {config.max_validation_attempts}")
        print(f"  Corruption threshold: {config.max_corrupted_objects}")
        print(f"  Performance metrics: {config.enable_performance_metrics}")
        print(f"  Expected concurrency: {config.max_expected_concurrency}")

        # Specific configuration by key
        print("\n--- Configuration by key ---")

        # Special configuration for large buffers
        _ = MemoryConfig(
            max_objects_per_key=5,  # Fewer large buffers
            ttl_seconds=300.0,  # Shorter TTL
            max_corrupted_objects=2,
        )

        # We can't directly set a configuration by size with BytesIOFactory
        # but we can show the principle
        print("Special configuration for large buffers defined")

        # Test with the configuration
        print("\n--- Testing the configuration ---")

        start_time = time.time()

        # Mixed test with small and large buffers
        for i in range(40):
            if i % 5 == 0:
                # Large buffer from time to time
                with pool.acquire_context(8192) as buffer:
                    buffer.write(f"Big buffer {i}".encode())
            else:
                # Small buffers most of the time
                with pool.acquire_context(1024) as buffer:
                    buffer.write(f"Small buffer {i}".encode())

        test_time = time.time() - start_time

        # Results
        stats = pool.get_basic_stats()
        print(f"Test finished in {test_time * 1000:.2f}ms")
        hits = stats["counters"].get("hits", 0)
        misses = stats["counters"].get("misses", 0)
        total = hits + misses
        hit_rate = (hits / total) if total else 0.0
        print(f"Hit rate: {hit_rate:.2%}")

        # Force a cleanup to test
        cleaned = pool.force_cleanup()
        print(f"Forced cleanup: {cleaned} objects cleaned")

        # Check health status with custom configuration
        health = pool.get_health_status()
        print(f"Health status: {health['status']}")

    finally:
        pool.shutdown()


if __name__ == "__main__":
    example_presets_configuration()
    example_automatic_optimization()
    example_real_time_monitoring()
    example_detailed_reports()
    example_custom_configuration()
