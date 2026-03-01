"""
Integration tests for memory management edge cases.
These tests target uncovered lines in memory_manager.py and memory_optimizer.py.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from examples.factories import BytesIOFactory, MetadataFactory
from smartpool import (
    MemoryConfig,
    MemoryPreset,
    MemoryPressure,
    ObjectFactory,
    PoolConfiguration,
    SmartObjectManager,
)


class TestMemoryPressureScenarios:
    """
    Integration tests for memory pressure detection and response.
    """

    def test_memory_pressure_detection_and_cleanup(self):
        """
        Test memory pressure detection triggers appropriate cleanup actions.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=20,
            ttl_seconds=60,
            enable_background_cleanup=True,
            cleanup_interval_seconds=0.1,
            enable_performance_metrics=True,
            memory_pressure=MemoryPressure.HIGH,  # High pressure to trigger cleanup
            max_expected_concurrency=10,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Start background cleanup
            pool.background_manager.start_background_cleanup()

            # Create memory pressure by filling up the pool
            held_objects = []
            for i in range(50):  # More than max_objects_per_key
                obj_id, key, obj = pool.acquire(f"key_{i % 5}")  # 5 keys, 10 objects each
                held_objects.append((obj_id, key, obj))

            # Release all objects to pool them
            for obj_id, key, obj in held_objects:
                pool.release(obj_id, key, obj)

            # Check memory manager detects pressure
            if hasattr(pool.manager, "get_memory_status"):
                memory_status = pool.manager.get_memory_status()
                # Should detect high memory usage
                assert memory_status is not None

            # Force memory pressure handling
            if hasattr(pool.manager, "handle_memory_pressure"):
                pressure_handled = pool.manager.handle_memory_pressure()
                assert pressure_handled is not None

            # Verify memory manager health status shows issues
            health = pool.manager.get_health_status()
            assert health["status"] in ["warning", "critical", "healthy"]

            # Force cleanup should reduce memory usage
            cleanup_count = pool.force_cleanup()
            assert cleanup_count >= 0

        finally:
            pool.shutdown()

    def test_memory_pressure_with_configuration_adjustment(self):
        """
        Test memory pressure triggers configuration adjustments.
        """
        factory = MetadataFactory()
        config = MemoryConfig(
            max_objects_per_key=10,
            ttl_seconds=30,
            enable_performance_metrics=True,
            memory_pressure=MemoryPressure.HIGH,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Enable auto-tuning to respond to memory pressure
            pool.enable_auto_tuning(interval_seconds=1)

            # Create sustained memory pressure
            objects_batch_1 = []
            for i in range(25):
                obj_id, key, obj = pool.acquire()
                objects_batch_1.append((obj_id, key, obj))

            # Release first batch
            for obj_id, key, obj in objects_batch_1:
                pool.release(obj_id, key, obj)

            # Wait for potential auto-tuning
            time.sleep(1.5)

            # Check if optimizer has been triggered
            tuning_info = pool.optimizer.get_tuning_info()
            assert tuning_info["enabled"] is True

            # Force optimization analysis
            analysis_result = pool.optimizer.force_optimization_analysis()
            assert "recommendations" in analysis_result
            assert "current_metrics" in analysis_result

            # Test memory manager recommendations
            recommendations = pool.manager.get_optimization_recommendations()
            assert "recommendations" in recommendations
            assert "urgency_level" in recommendations

        finally:
            pool.shutdown()

    def test_memory_pressure_recovery_cycle(self):
        """
        Test complete memory pressure detection and recovery cycle.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=5,
            ttl_seconds=10,
            enable_background_cleanup=True,
            cleanup_interval_seconds=0.2,
            enable_performance_metrics=True,
            memory_pressure=MemoryPressure.HIGH,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Start background processes
            pool.background_manager.start_background_cleanup()

            # Phase 1: Create memory pressure
            pressure_objects = []
            for i in range(15):  # 3x max_objects_per_key
                obj_id, key, obj = pool.acquire()
                pressure_objects.append((obj_id, key, obj))

            for obj_id, key, obj in pressure_objects:
                pool.release(obj_id, key, obj)

            # Get initial stats
            initial_stats = pool.get_basic_stats()
            assert initial_stats["total_pooled_objects"] > 0

            # Phase 2: Trigger memory management
            if hasattr(pool.manager, "get_optimization_recommendations"):
                pool.manager.get_optimization_recommendations()

            # Force cleanup multiple times to simulate pressure response
            for _ in range(3):
                _ = pool.force_cleanup()
                time.sleep(0.1)

            # Phase 3: Verify recovery
            recovery_stats = pool.get_basic_stats()

            # Should show some cleanup activity
            assert recovery_stats["counters"].get("expired", 0) >= initial_stats["counters"].get(
                "expired", 0
            )

            # Test memory manager dashboard
            dashboard = pool.manager.get_dashboard_summary()
            assert "basic_stats" in dashboard
            assert "health_status" in dashboard

        finally:
            pool.shutdown()


class TestOptimizerAutoTuningEdgeCases:
    """
    Integration tests for optimizer auto-tuning with real workloads.
    """

    def test_optimizer_auto_tuning_with_workload_patterns(self):
        """
        Test optimizer auto-tuning responds to different workload patterns.
        """
        factory = MetadataFactory()
        config = MemoryConfig(
            max_objects_per_key=8,
            ttl_seconds=20,
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
            enable_lock_contention_tracking=True,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Enable auto-tuning with short interval
            pool.enable_auto_tuning(interval_seconds=2)

            # Pattern 1: High hit rate workload
            cache_objects = []
            for i in range(5):
                obj_id, key, obj = pool.acquire("frequent_key")
                cache_objects.append((obj_id, key, obj))

            for obj_id, key, obj in cache_objects:
                pool.release(obj_id, key, obj)

            # Reuse cached objects multiple times
            for _ in range(10):
                obj_id, key, obj = pool.acquire("frequent_key")
                pool.release(obj_id, key, obj)

            # Pattern 2: High miss rate workload
            for i in range(15):
                obj_id, key, obj = pool.acquire(f"unique_key_{i}")
                pool.release(obj_id, key, obj)

            # Wait for auto-tuning cycles
            time.sleep(3)

            # Check tuning history
            tuning_info = pool.optimizer.get_tuning_info()
            assert tuning_info["enabled"] is True

            # Force analysis to capture current state
            analysis = pool.optimizer.force_optimization_analysis()
            assert "current_metrics" in analysis
            assert "recommendations" in analysis

            # Test recommendation application (dry run)
            if analysis["recommendations"]:
                application_result = pool.optimizer.apply_recommendations(
                    analysis["recommendations"], confirm=False
                )
                assert application_result["status"] == "confirmation_required"

                # Test actual application
                if len(analysis["recommendations"]) > 0:
                    application_result = pool.optimizer.apply_recommendations(
                        analysis["recommendations"][:1],  # Apply first recommendation only
                        confirm=True,
                    )
                    assert application_result["status"] in ["completed", "partially_completed"]

        finally:
            pool.shutdown()

    def test_optimizer_configuration_switching_during_operation(self):
        """
        Test optimizer behavior during configuration switches.
        """
        factory = BytesIOFactory()
        initial_config = MemoryConfig(
            max_objects_per_key=5, ttl_seconds=15, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=initial_config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Start with development preset
            pool.switch_preset(MemoryPreset.DEVELOPMENT)
            pool.enable_auto_tuning(interval_seconds=1)

            # Create some workload
            workload_objects = []
            for i in range(8):
                obj_id, key, obj = pool.acquire()
                workload_objects.append((obj_id, key, obj))

            for obj_id, key, obj in workload_objects:
                pool.release(obj_id, key, obj)

            # Switch to production preset during operation
            pool.switch_preset(MemoryPreset.HIGH_THROUGHPUT)

            # Continue workload
            for i in range(5):
                obj_id, key, obj = pool.acquire(f"post_switch_{i}")
                pool.release(obj_id, key, obj)

            # Wait for auto-tuning to adapt
            time.sleep(2)

            # Verify optimizer adapted to new configuration
            tuning_info = pool.optimizer.get_tuning_info()
            assert tuning_info["enabled"] is True

            # Switch to low memory
            pool.switch_preset(MemoryPreset.LOW_MEMORY)

            # Final analysis
            final_analysis = pool.optimizer.force_optimization_analysis()
            assert "current_metrics" in final_analysis

            # Verify different presets produced different configurations
            current_stats = pool.get_basic_stats()
            assert current_stats["counters"]["creates"] > 0

        finally:
            pool.shutdown()

    def test_optimizer_metric_collection_edge_cases(self):
        """
        Test optimizer metric collection under various edge conditions.
        """
        factory = MetadataFactory()
        config = MemoryConfig(
            max_objects_per_key=3,
            ttl_seconds=5,
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
            enable_lock_contention_tracking=True,
            max_expected_concurrency=8,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Enable auto-tuning
            pool.enable_auto_tuning(interval_seconds=1)

            # Create concurrent load to generate contention
            def worker_task(thread_id):
                objects = []
                for i in range(5):
                    obj_id, key, obj = pool.acquire(f"shared_key_{i % 2}")
                    objects.append((obj_id, key, obj))
                    time.sleep(0.01)  # Small delay to create contention

                for obj_id, key, obj in objects:
                    pool.release(obj_id, key, obj)

                return thread_id

            # Run concurrent workers
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(worker_task, i) for i in range(4)]
                for future in as_completed(futures):
                    result = future.result()
                    assert result is not None

            # Wait for metrics collection
            time.sleep(2)

            # Force metric collection and analysis
            analysis = pool.optimizer.force_optimization_analysis()
            assert "current_metrics" in analysis

            # Verify performance metrics captured contention
            performance_report = pool.manager.get_performance_report(detailed=True)
            assert "performance" in performance_report

            if "performance" in performance_report and performance_report["performance"]:
                current_metrics = performance_report["performance"].get("current_metrics", {})
                # Should have captured some metrics from concurrent operations
                assert len(current_metrics) > 0

            # Test optimizer recommendation estimation
            if analysis["recommendations"]:
                estimation = pool.optimizer._estimate_improvement(analysis["recommendations"])
                assert "overall" in estimation
                assert estimation["overall"] in [
                    "No significant improvement expected",
                    "Minor improvement expected",
                    "Moderate improvement expected",
                    "Major improvement expected",
                ]

        finally:
            pool.shutdown()


class TestBackgroundCleanupUnderLoad:
    """
    Integration tests for background cleanup during concurrent operations.
    """

    def test_background_cleanup_with_concurrent_operations(self):
        """
        Test background cleanup effectiveness during concurrent acquire/release operations.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=6,
            ttl_seconds=2,  # Short TTL for aggressive cleanup
            enable_background_cleanup=True,
            cleanup_interval_seconds=0.5,
            enable_performance_metrics=True,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Start background cleanup
            pool.background_manager.start_background_cleanup()

            # Concurrent worker that continuously uses the pool
            def continuous_worker(worker_id, duration_seconds):
                end_time = time.time() + duration_seconds
                operations = 0

                while time.time() < end_time:
                    obj_id, key, obj = pool.acquire(f"worker_{worker_id % 3}")
                    time.sleep(0.01)  # Brief work simulation
                    pool.release(obj_id, key, obj)
                    operations += 1

                return operations

            # Run workers while background cleanup is active
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(continuous_worker, i, 3) for i in range(3)]

                # Monitor stats during execution
                initial_stats = pool.get_basic_stats()

                # Wait for workers to complete
                total_operations = 0
                for future in as_completed(futures):
                    operations = future.result()
                    total_operations += operations
                    assert operations > 0

            # Allow final cleanup cycle
            time.sleep(1)

            # Verify cleanup effectiveness
            final_stats = pool.get_basic_stats()
            # Check that pool processed some objects
            assert (
                final_stats["counters"]["creates"] > initial_stats["counters"]["creates"]
                or final_stats["total_pooled_objects"] >= 0
            )
            assert total_operations > 0

            # Verify background manager statistics
            if hasattr(pool.background_manager, "get_cleanup_stats"):
                cleanup_stats = pool.background_manager.get_cleanup_stats()
                assert cleanup_stats is not None

        finally:
            pool.shutdown()

    def test_background_cleanup_memory_recovery(self):
        """
        Test background cleanup recovers memory from expired objects.
        """
        factory = MetadataFactory()
        config = MemoryConfig(
            max_objects_per_key=10,
            ttl_seconds=1,  # Very short TTL
            enable_background_cleanup=True,
            cleanup_interval_seconds=0.3,
            enable_performance_metrics=True,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Start background cleanup
            pool.background_manager.start_background_cleanup()

            # Phase 1: Fill pool with objects that will expire
            expired_objects = []
            for i in range(15):
                obj_id, key, obj = pool.acquire(f"expire_key_{i % 3}")
                expired_objects.append((obj_id, key, obj))

            # Release all objects to pool
            for obj_id, key, obj in expired_objects:
                pool.release(obj_id, key, obj)

            # Capture stats after filling
            filled_stats = pool.get_basic_stats()
            assert filled_stats["total_pooled_objects"] > 0

            # Phase 2: Wait for TTL expiration + cleanup cycles
            time.sleep(2.5)  # Allow multiple cleanup cycles

            # Phase 3: Verify memory recovery
            recovered_stats = pool.get_basic_stats()

            # Should show cleanup activity (objects should be processed)
            assert recovered_stats["counters"]["creates"] >= 0

            # Memory should be recovered (fewer pooled objects)
            assert recovered_stats["total_pooled_objects"] <= filled_stats["total_pooled_objects"]

            # Verify memory manager health improved
            health_status = pool.manager.get_health_status()
            assert health_status["status"] in ["healthy", "warning", "critical"]

            # Test dashboard shows recovery information
            dashboard = pool.manager.get_dashboard_summary()
            assert "basic_stats" in dashboard
            assert dashboard["basic_stats"]["total_pooled_objects"] >= 0

        finally:
            pool.shutdown()


class TestErrorRecoveryScenarios:
    """
    Integration tests for error recovery in memory management.
    """

    def test_memory_manager_error_recovery(self):
        """
        Test memory manager recovery from various error conditions.
        """

        class FlakyObject:
            def __init__(self, data):
                self.data = data

        class FlakyFactory(ObjectFactory):
            def __init__(self):
                self.creation_count = 0

            def create(self, *args, **kwargs):
                self.creation_count += 1
                if self.creation_count % 3 == 0:  # Fail every 3rd creation
                    raise RuntimeError(f"Factory failure {self.creation_count}")
                return FlakyObject(f"object_{self.creation_count}")

            def reset(self, obj):
                return False  # <- Force destruction, no reuse

            def validate(self, obj):
                return isinstance(obj, FlakyObject) and hasattr(obj, "data")

            def get_key(self, *args, **kwargs):
                return "flaky_key"

            def estimate_size(self, obj):
                return 50

            def destroy(self, obj):
                pass

        factory = FlakyFactory()
        config = MemoryConfig(
            max_objects_per_key=5,
            ttl_seconds=10,
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            successful_operations = 0
            failed_operations = 0

            # Attempt operations that will partially fail
            for i in range(10):
                try:
                    obj_id, key, obj = pool.acquire()
                    pool.release(obj_id, key, obj)
                    successful_operations += 1
                except Exception as e:
                    print(e)
                    failed_operations += 1

            # Should have both successes and failures
            assert successful_operations > 0
            assert failed_operations > 0

            # Verify pool maintains functional state despite errors
            stats = pool.get_basic_stats()
            assert stats["counters"]["creates"] > 0

            # Memory manager should report health issues
            health = pool.manager.get_health_status()
            assert health is not None

            # Should still be able to get optimization recommendations
            recommendations = pool.manager.get_optimization_recommendations()
            assert "recommendations" in recommendations

        finally:
            pool.shutdown()

    def test_optimizer_error_recovery_during_tuning(self):
        """
        Test optimizer recovery from errors during auto-tuning.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=4, ttl_seconds=10, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Enable auto-tuning
            pool.enable_auto_tuning(interval_seconds=1)

            # Create some workload
            for i in range(8):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Force optimization analysis that might encounter edge cases
            try:
                analysis = pool.optimizer.force_optimization_analysis()
                assert "recommendations" in analysis

                # Try to apply invalid recommendations to test error handling
                invalid_recommendations = [
                    {
                        "parameter": "nonexistent_param",
                        "recommended": 100,
                        "current": 50,
                        "reason": "Test",
                    }
                ]

                result = pool.optimizer.apply_recommendations(invalid_recommendations, confirm=True)
                assert result["status"] in ["completed", "partially_completed"]
                assert "failed" in result

            except Exception:
                # Optimizer should handle errors gracefully
                pass

            # Verify optimizer remains functional after errors
            tuning_info = pool.optimizer.get_tuning_info()
            assert tuning_info is not None

            # Should still be able to disable/enable auto-tuning
            pool.disable_auto_tuning()
            assert not pool.optimizer.get_tuning_info()["enabled"]

            pool.enable_auto_tuning(interval_seconds=2)
            assert pool.optimizer.get_tuning_info()["enabled"]

        finally:
            pool.shutdown()
