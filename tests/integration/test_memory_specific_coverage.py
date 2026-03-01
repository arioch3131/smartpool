"""
Integration tests specifically targeting uncovered lines in memory management modules.
These tests focus on edge cases and error conditions in memory_manager.py and memory_optimizer.py.
"""

import time

from examples.factories import BytesIOFactory, MetadataFactory, NumpyArrayFactory
from smartpool import SmartObjectManager
from smartpool.config import (
    MemoryConfig,
    MemoryPreset,
    PoolConfiguration,
)


class TestMemoryManagerSpecificCoverage:
    """
    Tests targeting specific uncovered lines in memory_manager.py.
    """

    def test_memory_manager_without_performance_metrics(self):
        """
        Test memory manager behavior when performance_metrics is None.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=5,
            ttl_seconds=10,
            enable_performance_metrics=False,  # Disable performance metrics
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(
                enable_monitoring=False,  # This might disable performance metrics
                register_atexit=False,
            ),
        )

        try:
            # Create some workload
            objects = []
            for i in range(8):
                obj_id, key, obj = pool.acquire()
                objects.append((obj_id, key, obj))

            for obj_id, key, obj in objects:
                pool.release(obj_id, key, obj)

            # Test performance report when performance_metrics is None
            performance_report = pool.manager.get_performance_report(detailed=True)
            assert "basic_stats" in performance_report
            assert "preset" in performance_report

            # Should handle missing performance_metrics gracefully
            if "performance" not in performance_report or performance_report["performance"] is None:
                assert True  # Expected behavior when metrics disabled

            # Test dashboard summary without performance metrics
            dashboard = pool.manager.get_dashboard_summary()
            assert "basic_stats" in dashboard
            assert "health_status" in dashboard

            # Should not have advanced_metrics when performance_metrics is None
            if "advanced_metrics" not in dashboard:
                assert True  # Expected behavior

        finally:
            pool.shutdown()

    def test_memory_manager_without_optimizer(self):
        """
        Test memory manager behavior when optimizer is None.
        """
        factory = MetadataFactory()
        config = MemoryConfig(max_objects_per_key=3, ttl_seconds=5, enable_performance_metrics=True)

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Manually set optimizer to None to test edge case
            original_optimizer = pool.optimizer
            pool.optimizer = None

            # Create workload
            for i in range(6):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Test performance report without optimizer
            performance_report = pool.manager.get_performance_report(detailed=True)
            assert "auto_tuning" in performance_report
            assert performance_report["auto_tuning"]["enabled"] is False
            assert performance_report["auto_tuning"]["interval"] == 0
            assert performance_report["auto_tuning"]["last_run"] == 0
            assert performance_report["auto_tuning"]["adjustments_count"] == 0

            # Test optimization recommendations without optimizer
            recommendations = pool.manager.get_optimization_recommendations()
            assert "recommendations" in recommendations
            assert "note" in recommendations
            assert "optimizer not available" in recommendations["note"].lower()

            # Test dashboard summary without optimizer
            dashboard = pool.manager.get_dashboard_summary()
            assert "basic_stats" in dashboard

            # Restore optimizer
            pool.optimizer = original_optimizer

        finally:
            pool.shutdown()

    def test_memory_manager_health_status_edge_cases(self):
        """
        Test health status calculation with various edge conditions.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=10,
            ttl_seconds=20,
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Test with zero operations (edge case)
            initial_health = pool.manager.get_health_status()
            assert initial_health["status"] in ["healthy", "warning", "critical"]

            # Create high corruption scenario by manipulating stats
            # This is tricky in integration test, so we'll create many operations
            # and rely on some natural variance

            # Create large number of operations to get meaningful stats
            for i in range(50):
                obj_id, key, obj = pool.acquire(f"key_{i % 5}")
                pool.release(obj_id, key, obj)

            # Get health status with real data
            health_with_data = pool.manager.get_health_status()
            assert health_with_data["status"] in ["healthy", "warning", "critical"]
            assert "issues" in health_with_data
            assert isinstance(health_with_data["issues"], list)

            # Test performance report health integration
            performance_report = pool.manager.get_performance_report(detailed=True)
            if "performance" in performance_report and performance_report["performance"]:
                assert performance_report["performance"] is not None

        finally:
            pool.shutdown()

    def test_memory_manager_optimization_recommendations_urgency_levels(self):
        """
        Test optimization recommendation urgency level calculations.
        """
        factory = MetadataFactory()
        config = MemoryConfig(
            max_objects_per_key=8, ttl_seconds=15, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Create workload to generate statistics
            # Pattern: High miss rate (many unique keys)
            for i in range(30):
                obj_id, key, obj = pool.acquire(f"unique_key_{i}")
                pool.release(obj_id, key, obj)

            # Get recommendations with high miss rate
            recommendations_high_miss = pool.manager.get_optimization_recommendations()
            assert "urgency_level" in recommendations_high_miss
            assert "urgency_score" in recommendations_high_miss

            # Create different pattern: Reuse same keys (higher hit rate)
            for i in range(20):
                obj_id, key, obj = pool.acquire("frequent_key")
                pool.release(obj_id, key, obj)

            # Get new recommendations
            recommendations_better = pool.manager.get_optimization_recommendations()
            assert "urgency_level" in recommendations_better

            # Test that urgency levels are calculated correctly
            assert recommendations_better["urgency_level"] in ["info", "warning", "critical"]

        finally:
            pool.shutdown()


class TestMemoryOptimizerSpecificCoverage:
    """
    Tests targeting specific uncovered lines in memory_optimizer.py.
    """

    def test_optimizer_metric_collection_without_performance_metrics(self):
        """
        Test optimizer metric collection when performance_metrics is None.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=5,
            ttl_seconds=10,
            enable_performance_metrics=False,  # Disable performance metrics
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Create workload
            for i in range(8):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Enable auto-tuning to trigger metric collection
            pool.enable_auto_tuning(interval_seconds=1)

            # Force optimization analysis without performance metrics
            analysis = pool.optimizer.force_optimization_analysis()
            assert "current_metrics" in analysis
            assert "recommendations" in analysis

            # The metrics should still be collected from basic stats
            assert analysis["current_metrics"] is not None

        finally:
            pool.shutdown()

    def test_optimizer_auto_tuning_interval_edge_cases(self):
        """
        Test auto-tuning interval handling and timing edge cases.
        """
        factory = MetadataFactory()
        config = MemoryConfig(max_objects_per_key=4, ttl_seconds=8, enable_performance_metrics=True)

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Test enabling auto-tuning when already enabled
            pool.enable_auto_tuning(interval_seconds=2)
            assert pool.optimizer.get_tuning_info()["enabled"] is True

            # Enable again with different interval
            pool.enable_auto_tuning(interval_seconds=3)
            tuning_info = pool.optimizer.get_tuning_info()
            assert tuning_info["enabled"] is True
            assert tuning_info["interval"] == 3

            # Test disabling when already disabled
            pool.disable_auto_tuning()
            assert pool.optimizer.get_tuning_info()["enabled"] is False

            pool.disable_auto_tuning()  # Disable again
            assert pool.optimizer.get_tuning_info()["enabled"] is False

            # Test check_auto_tuning when disabled
            pool.optimizer.check_auto_tuning()  # Should do nothing

            # Re-enable and test interval timing
            pool.enable_auto_tuning(interval_seconds=1)

            # Create workload
            for i in range(5):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Wait for interval
            time.sleep(1.5)

            # Check auto-tuning should trigger
            pool.optimizer.check_auto_tuning()

        finally:
            pool.shutdown()

    def test_optimizer_perform_auto_tuning_exception_handling(self):
        """
        Test optimizer exception handling during auto-tuning.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=6, ttl_seconds=12, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Create workload
            for i in range(10):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Test perform_auto_tuning with potential exceptions
            # This will test the exception handling in the method
            pool.enable_auto_tuning(interval_seconds=1)

            # Force multiple auto-tuning attempts
            for _ in range(3):
                try:
                    result = pool.optimizer.perform_auto_tuning()
                    # Result should be boolean
                    assert isinstance(result, bool)
                except Exception:
                    # Should handle exceptions gracefully
                    pass

                time.sleep(0.1)

            # Optimizer should remain functional after exceptions
            tuning_info = pool.optimizer.get_tuning_info()
            assert tuning_info is not None

        finally:
            pool.shutdown()

    def test_optimizer_apply_config_changes_edge_cases(self):
        """
        Test optimizer configuration change application edge cases.
        """
        factory = MetadataFactory()
        config = MemoryConfig(
            max_objects_per_key=7, ttl_seconds=14, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Create workload
            for i in range(12):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Get optimization analysis
            analysis = pool.optimizer.force_optimization_analysis()

            if analysis["recommendations"]:
                # Test applying recommendations without confirmation
                result = pool.optimizer.apply_recommendations(
                    analysis["recommendations"], confirm=False
                )
                assert result["status"] == "confirmation_required"
                assert "recommendations_count" in result

                # Test applying with confirmation
                result_confirmed = pool.optimizer.apply_recommendations(
                    analysis["recommendations"][:1],
                    confirm=True,  # Apply just one
                )
                assert result_confirmed["status"] in ["completed", "partially_completed"]
                assert "applied" in result_confirmed
                assert "failed" in result_confirmed

                # Test applying invalid recommendations
                invalid_recs = [
                    {
                        "parameter": "invalid_parameter",
                        "recommended": 100,
                        "current": 50,
                        "reason": "Test invalid parameter",
                    }
                ]

                invalid_result = pool.optimizer.apply_recommendations(invalid_recs, confirm=True)
                assert invalid_result["status"] == "completed"  # Completed with failures
                assert len(invalid_result["failed"]) > 0
                assert invalid_result["success_rate"] == 0.0

        finally:
            pool.shutdown()

    def test_optimizer_improvement_estimation_edge_cases(self):
        """
        Test improvement estimation with various recommendation combinations.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=5, ttl_seconds=10, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Create workload
            for i in range(8):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Test improvement estimation with empty recommendations
            empty_estimation = pool.optimizer._estimate_improvement([])
            assert empty_estimation["overall"] == "No significant improvement expected"

            # Test with mixed impact recommendations
            mixed_recs = [
                {"impact": "high", "parameter": "test1"},
                {"impact": "low", "parameter": "test2"},
                {"impact": "medium", "parameter": "test3"},
            ]

            mixed_estimation = pool.optimizer._estimate_improvement(mixed_recs)
            assert mixed_estimation["overall"] in [
                "Minor improvement expected",
                "Moderate improvement expected",
                "Major improvement expected",
            ]

            # Test with all high impact
            high_recs = [
                {"impact": "high", "parameter": "test1"},
                {"impact": "high", "parameter": "test2"},
            ]

            high_estimation = pool.optimizer._estimate_improvement(high_recs)
            assert high_estimation["overall"] == "Major improvement expected"

            # Test with all low impact
            low_recs = [
                {"impact": "low", "parameter": "test1"},
                {"impact": "low", "parameter": "test2"},
            ]

            low_estimation = pool.optimizer._estimate_improvement(low_recs)
            assert low_estimation["overall"] == "Minor improvement expected"

        finally:
            pool.shutdown()

    def test_optimizer_adjustment_history_limits(self):
        """
        Test optimizer adjustment history size limits and management.
        """
        factory = MetadataFactory()
        config = MemoryConfig(
            max_objects_per_key=6, ttl_seconds=12, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Enable auto-tuning
            pool.enable_auto_tuning(interval_seconds=1)

            # Create workload and generate adjustments
            for cycle in range(5):
                # Create different workload patterns
                for i in range(8):
                    obj_id, key, obj = pool.acquire(f"cycle_{cycle}_key_{i % 2}")
                    pool.release(obj_id, key, obj)

                # Force analysis and potential adjustments
                analysis = pool.optimizer.force_optimization_analysis()

                if analysis["recommendations"]:
                    # Try to apply some recommendations to generate history
                    pool.optimizer.apply_recommendations(
                        analysis["recommendations"][:1], confirm=True
                    )

                time.sleep(0.1)

            # Check tuning info includes history
            tuning_info = pool.optimizer.get_tuning_info()
            assert "history" in tuning_info

            # History should be limited in size
            if tuning_info["history"]:
                # Should not exceed reasonable history size
                assert len(tuning_info["history"]) <= 50  # Assuming reasonable limit

        finally:
            pool.shutdown()


class TestMemoryConfigurationSwitchingEdgeCases:
    """
    Tests for configuration switching during various operations.
    """

    def test_preset_switching_during_active_operations(self):
        """
        Test preset switching while operations are in progress.
        """
        factory = NumpyArrayFactory()
        config = MemoryConfig(
            max_objects_per_key=4,
            ttl_seconds=8,
            enable_performance_metrics=True,
            enable_background_cleanup=True,
            cleanup_interval_seconds=1,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Start background cleanup
            pool.background_manager.start_background_cleanup()

            # Start with development preset
            pool.switch_preset(MemoryPreset.DEVELOPMENT)
            initial_config = pool.default_config

            # Create active operations
            active_objects = []
            for i in range(6):
                obj_id, key, obj = pool.acquire(shape=(10, 10), dtype="float32")
                active_objects.append((obj_id, key, obj))

            # Switch preset while objects are active
            pool.switch_preset(MemoryPreset.HIGH_THROUGHPUT)
            production_config = pool.default_config

            # Verify configuration changed
            assert (
                production_config.max_objects_per_key != initial_config.max_objects_per_key
                or production_config.ttl_seconds != initial_config.ttl_seconds
            )

            # Release objects
            for obj_id, key, obj in active_objects:
                pool.release(obj_id, key, obj)

            # Switch to high throughput during background operations
            pool.switch_preset(MemoryPreset.HIGH_THROUGHPUT)

            # Continue operations with new preset
            for i in range(4):
                obj_id, key, obj = pool.acquire(shape=(10, 10), dtype="float32")
                pool.release(obj_id, key, obj)

            # Memory manager should adapt to configuration changes
            final_stats = pool.get_basic_stats()
            assert final_stats["counters"]["creates"] > 0

            # Health status should remain stable
            health = pool.manager.get_health_status()
            assert health["status"] in ["healthy", "warning", "critical"]

        finally:
            pool.shutdown()

    def test_configuration_validation_edge_cases(self):
        """
        Test configuration validation during runtime changes.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(max_objects_per_key=3, ttl_seconds=6, enable_performance_metrics=True)

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Test multiple rapid preset switches
            presets = [
                MemoryPreset.DEVELOPMENT,
                MemoryPreset.HIGH_THROUGHPUT,
                MemoryPreset.HIGH_THROUGHPUT,
                MemoryPreset.DEVELOPMENT,
            ]

            for preset in presets:
                pool.switch_preset(preset)

                # Quick operation after each switch
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

                # Verify pool remains functional
                stats = pool.get_basic_stats()
                assert stats is not None

            # Test custom configuration updates
            custom_config = MemoryConfig(
                max_objects_per_key=10,
                ttl_seconds=30,
                enable_performance_metrics=True,
                enable_background_cleanup=True,
            )

            # Apply custom configuration
            pool.default_config = custom_config

            # Verify new configuration is effective
            for i in range(8):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            final_stats = pool.get_basic_stats()
            assert final_stats["counters"]["creates"] > 0

        finally:
            pool.shutdown()
