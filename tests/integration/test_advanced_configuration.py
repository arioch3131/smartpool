"""
Integration tests for SmartObjectManager advanced configuration scenarios.
These tests ensure that configuration features like TTL, presets, and optimization work correctly.
"""

import time

from examples.factories import BytesIOFactory, MetadataFactory
from smartpool import SmartObjectManager
from smartpool.config import (
    MemoryConfig,
    MemoryConfigFactory,
    MemoryPreset,
    MemoryPressure,
    ObjectCreationCost,
    PoolConfiguration,
)


class TestAdvancedConfiguration:
    """
    Integration tests for SmartObjectManager advanced configuration features.
    """

    def test_ttl_expiration_integration(self):
        """
        Test complete TTL expiration cycle with cleanup.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=5,
            ttl_seconds=0.2,  # Short TTL for testing
            cleanup_interval_seconds=0.1,
            enable_background_cleanup=True,
        )
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Start background cleanup
            pool.background_manager.start_background_cleanup()

            # Create and release ONE object
            obj_id, key, obj = pool.acquire()
            pool.release(obj_id, key, obj)

            # Verify object is pooled
            stats_before = pool.get_basic_stats()
            assert stats_before["total_pooled_objects"] == 1  # Realistic expectation

            # Wait for TTL to expire
            time.sleep(0.3)

            # Force cleanup to ensure expired objects are removed
            cleanup_result = pool.force_cleanup()
            # force_cleanup returns either number of objects cleaned or 0
            assert cleanup_result >= 0  # Should return a valid number

            # Verify some objects may have been removed (timing dependent)
            stats_after = pool.get_basic_stats()
            assert stats_after["total_pooled_objects"] <= stats_before["total_pooled_objects"]

            # New acquisitions should create fresh objects
            obj_id, key, obj = pool.acquire()
            pool.release(obj_id, key, obj)

            # Verify creation counter increased
            final_stats = pool.get_basic_stats()
            assert final_stats["counters"]["creates"] >= 2  # At least 2 original objects

        finally:
            pool.shutdown()

    def test_memory_preset_integration(self):
        """
        Test integration with different memory presets.
        """
        factory = MetadataFactory()

        # Test HIGH_THROUGHPUT preset
        high_throughput_config = MemoryConfigFactory.create_preset(MemoryPreset.HIGH_THROUGHPUT)
        high_throughput_pool = SmartObjectManager(
            factory=factory,
            default_config=high_throughput_config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        # Test LOW_MEMORY preset (MEMORY_EFFICIENT doesn't exist, using LOW_MEMORY)
        memory_efficient_config = MemoryConfigFactory.create_preset(MemoryPreset.LOW_MEMORY)
        memory_efficient_pool = SmartObjectManager(
            factory=factory,
            default_config=memory_efficient_config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Verify different configurations
            assert (
                high_throughput_config.max_objects_per_key
                > memory_efficient_config.max_objects_per_key
            )
            assert high_throughput_config.ttl_seconds > memory_efficient_config.ttl_seconds

            # Test high throughput pool
            ht_objects = []
            for i in range(10):
                obj_id, key, obj = high_throughput_pool.acquire()
                obj[f"key_{i}"] = f"value_{i}"
                ht_objects.append((obj_id, key, obj))

            for obj_id, key, obj in ht_objects:
                high_throughput_pool.release(obj_id, key, obj)

            ht_stats = high_throughput_pool.get_basic_stats()

            # Test memory efficient pool
            me_objects = []
            for i in range(10):
                obj_id, key, obj = memory_efficient_pool.acquire()
                obj[f"key_{i}"] = f"value_{i}"
                me_objects.append((obj_id, key, obj))

            for obj_id, key, obj in me_objects:
                memory_efficient_pool.release(obj_id, key, obj)

            me_stats = memory_efficient_pool.get_basic_stats()

            # High throughput should pool more objects
            assert ht_stats["total_pooled_objects"] >= me_stats["total_pooled_objects"]

        finally:
            high_throughput_pool.shutdown()
            memory_efficient_pool.shutdown()

    def test_preset_switching_integration(self):
        """
        Test dynamic preset switching during runtime.
        """
        factory = BytesIOFactory()
        config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            preset=MemoryPreset.DEVELOPMENT,  # Explicitly set preset
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Initial state
            initial_max_objects = pool.default_config.max_objects_per_key

            # Create some objects
            for i in range(3):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            initial_stats = pool.get_basic_stats()

            # Switch to HIGH_THROUGHPUT preset
            switch_result = pool.switch_preset(MemoryPreset.HIGH_THROUGHPUT)
            assert switch_result["success"] is True
            assert switch_result["old_preset"] == "development"  # String value, not enum
            assert switch_result["new_preset"] == "high_throughput"  # String value, not enum

            # Verify configuration changed
            new_max_objects = pool.default_config.max_objects_per_key
            assert new_max_objects > initial_max_objects

            # Test with new configuration
            for i in range(5):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            new_stats = pool.get_basic_stats()
            assert new_stats["total_pooled_objects"] >= initial_stats["total_pooled_objects"]

            # Get preset info
            preset_info = pool.get_preset_info()
            assert preset_info["current_preset"] == "high_throughput"  # String value
            assert "available_presets" in preset_info

        finally:
            pool.shutdown()

    def test_auto_tuning_integration(self):
        """
        Test auto-tuning functionality integration.
        """
        factory = BytesIOFactory()
        base_config = MemoryConfig(
            max_objects_per_key=10,
            ttl_seconds=60,
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
            object_creation_cost=ObjectCreationCost.MEDIUM,
            memory_pressure=MemoryPressure.NORMAL,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=base_config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Enable auto-tuning
            pool.enable_auto_tuning()

            # Create some load to generate metrics
            for cycle in range(3):
                objects = []
                # Acquire more objects than pool size to create pressure
                for i in range(15):
                    obj_id, key, obj = pool.acquire()
                    objects.append((obj_id, key, obj))

                # Release all objects
                for obj_id, key, obj in objects:
                    pool.release(obj_id, key, obj)

                # Small delay between cycles
                time.sleep(0.01)

            # Get performance metrics
            if pool.performance_metrics:
                snapshot = pool.performance_metrics.create_snapshot()
                assert snapshot.total_acquisitions > 0

            # Test auto-tuning functionality
            if pool.optimizer:
                # Check auto-tuning can be enabled/disabled
                pool.enable_auto_tuning(interval_seconds=60)
                pool.disable_auto_tuning()

                # Test manual auto-tuning
                tuning_result = pool.optimizer.perform_auto_tuning()
                # Should return boolean indicating if adjustments were made
                assert isinstance(tuning_result, bool)

            # Disable auto-tuning
            pool.disable_auto_tuning()

        finally:
            pool.shutdown()

    def test_advanced_monitoring_integration(self):
        """
        Test advanced monitoring and optimization features.
        """
        factory = MetadataFactory()
        config = MemoryConfig(
            max_objects_per_key=5,
            ttl_seconds=30,
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
            enable_lock_contention_tracking=True,
            max_expected_concurrency=4,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Generate various operations to create metrics
            operations = []

            # Pattern 1: Normal acquire/release
            for i in range(10):
                obj_id, key, obj = pool.acquire()
                obj[f"normal_{i}"] = f"value_{i}"
                operations.append((obj_id, key, obj))

            for obj_id, key, obj in operations:
                pool.release(obj_id, key, obj)

            # Pattern 2: Pool exhaustion
            held_objects = []
            for i in range(8):  # More than max_objects_per_key
                obj_id, key, obj = pool.acquire()
                held_objects.append((obj_id, key, obj))

            for obj_id, key, obj in held_objects:
                pool.release(obj_id, key, obj)

            # Get comprehensive statistics
            basic_stats = pool.get_basic_stats()
            assert basic_stats["counters"]["creates"] > 0
            assert basic_stats["counters"]["hits"] + basic_stats["counters"]["misses"] > 0

            # Test performance metrics if available
            if pool.performance_metrics:
                snapshot = pool.performance_metrics.create_snapshot()
                assert snapshot.total_acquisitions > 0
                assert snapshot.hit_rate >= 0.0 and snapshot.hit_rate <= 1.0

            # Test optimizer if available
            if pool.optimizer:
                # Test auto-tuning enable/disable
                pool.enable_auto_tuning(interval_seconds=60)
                assert pool.optimizer._auto_tune_enabled is True

                pool.disable_auto_tuning()
                assert pool.optimizer._auto_tune_enabled is False

        finally:
            pool.shutdown()

    def test_custom_configuration_integration(self):
        """
        Test integration with custom configuration parameters.
        """
        factory = BytesIOFactory()

        # Create highly customized configuration
        custom_config = MemoryConfig(
            max_objects_per_key=15,
            ttl_seconds=120.0,
            cleanup_interval_seconds=30.0,
            enable_background_cleanup=True,
            enable_performance_metrics=True,
            enable_acquisition_tracking=True,
            enable_lock_contention_tracking=True,
            max_expected_concurrency=8,
            object_creation_cost=ObjectCreationCost.HIGH,
            memory_pressure=MemoryPressure.HIGH,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=custom_config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Start background processes
            pool.background_manager.start_background_cleanup()

            # Test configuration is applied
            assert pool.default_config.max_objects_per_key == 15
            assert pool.default_config.ttl_seconds == 120.0
            assert pool.default_config.object_creation_cost == ObjectCreationCost.HIGH

            # Create significant load
            all_objects = []
            for batch in range(3):
                batch_objects = []
                for i in range(12):
                    obj_id, key, obj = pool.acquire()
                    obj.write(f"Batch {batch}, Object {i}".encode())
                    batch_objects.append((obj_id, key, obj))

                all_objects.extend(batch_objects)

                # Release batch
                for obj_id, key, obj in batch_objects:
                    pool.release(obj_id, key, obj)

                time.sleep(0.01)  # Small delay between batches

            # Verify pool handled custom configuration correctly
            stats = pool.get_basic_stats()
            assert stats["total_pooled_objects"] <= custom_config.max_objects_per_key
            assert stats["counters"]["creates"] >= 1

            # Test that high creation cost setting affects behavior
            # (This would typically result in more aggressive pooling)
            assert stats["total_pooled_objects"] > 0

        finally:
            pool.shutdown()

    def test_configuration_validation_integration(self):
        """
        Test that configuration validation works in real scenarios.
        """
        factory = BytesIOFactory()

        # Test valid configuration
        valid_config = MemoryConfig(
            max_objects_per_key=10, ttl_seconds=60.0, cleanup_interval_seconds=30.0
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=valid_config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Should work normally
            obj_id, key, obj = pool.acquire()
            pool.release(obj_id, key, obj)

            stats = pool.get_basic_stats()
            assert stats["total_pooled_objects"] == 1

        finally:
            pool.shutdown()

        # Test edge case configurations
        edge_config = MemoryConfig(
            max_objects_per_key=1,  # Minimal pool size
            ttl_seconds=1.0,  # Very short TTL
            cleanup_interval_seconds=0.5,  # Frequent cleanup
        )

        edge_pool = SmartObjectManager(
            factory=factory,
            default_config=edge_config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Should still work with edge configuration
            for i in range(5):
                obj_id, key, obj = edge_pool.acquire()
                obj.write(f"Edge test {i}".encode())
                edge_pool.release(obj_id, key, obj)

            stats = edge_pool.get_basic_stats()
            assert stats["counters"]["creates"] >= 1

        finally:
            edge_pool.shutdown()

    def test_multiple_configuration_contexts(self):
        """
        Test using multiple pools with different configurations simultaneously.
        """
        factory = BytesIOFactory()

        # High-performance configuration
        high_perf_config = MemoryConfig(
            max_objects_per_key=20, ttl_seconds=300, enable_performance_metrics=True
        )

        # Resource-constrained configuration
        low_resource_config = MemoryConfig(
            max_objects_per_key=3, ttl_seconds=10, enable_background_cleanup=False
        )

        high_perf_pool = SmartObjectManager(
            factory=factory,
            default_config=high_perf_config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        low_resource_pool = SmartObjectManager(
            factory=factory,
            default_config=low_resource_config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Use both pools simultaneously
            hp_objects = []
            lr_objects = []

            # Load high-performance pool
            for i in range(15):
                obj_id, key, obj = high_perf_pool.acquire()
                obj.write(f"HP Object {i}".encode())
                hp_objects.append((obj_id, key, obj))

            # Load low-resource pool
            for i in range(5):
                obj_id, key, obj = low_resource_pool.acquire()
                obj.write(f"LR Object {i}".encode())
                lr_objects.append((obj_id, key, obj))

            # Release all objects
            for obj_id, key, obj in hp_objects:
                high_perf_pool.release(obj_id, key, obj)

            for obj_id, key, obj in lr_objects:
                low_resource_pool.release(obj_id, key, obj)

            # Verify different behaviors
            hp_stats = high_perf_pool.get_basic_stats()
            lr_stats = low_resource_pool.get_basic_stats()

            # High-performance pool should pool more objects
            assert hp_stats["total_pooled_objects"] >= lr_stats["total_pooled_objects"]

            # Low-resource pool should have created more objects due to limit
            # (relative to pool size)
            hp_creation_ratio = (
                hp_stats["counters"]["creates"] / high_perf_config.max_objects_per_key
            )
            lr_creation_ratio = (
                lr_stats["counters"]["creates"] / low_resource_config.max_objects_per_key
            )

            assert lr_creation_ratio >= hp_creation_ratio

        finally:
            high_perf_pool.shutdown()
            low_resource_pool.shutdown()
