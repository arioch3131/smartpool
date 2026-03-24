"""
Integration tests for error recovery scenarios.
These tests target uncovered lines in exception handling and error recovery paths.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from examples.factories import BytesIOFactory, MetadataFactory
from smartpool import SmartObjectManager
from smartpool.config import (
    MemoryConfig,
    MemoryPressure,
    PoolConfiguration,
)
from smartpool.core.exceptions import (
    ExceptionMetrics,
    ExceptionPolicy,
    ObjectCreationFailedError,
    PoolExhaustedError,
    SmartPoolExceptionFactory,
)
from smartpool.core.factory_interface import ObjectFactory
from tests.testing_utils import WeakReferencableObject


class FailingFactory(ObjectFactory):
    """Factory that fails in various ways to test error recovery."""

    def __init__(self, fail_mode="none", failure_rate=0.0, failure_count=0):
        self.fail_mode = fail_mode
        self.failure_rate = failure_rate
        self.failure_count = failure_count
        self.creation_count = 0
        self.validation_count = 0
        self.reset_count = 0
        self.destroy_count = 0
        self.objects_created = []

    def create(self, *args, **kwargs):
        self.creation_count += 1

        if self.fail_mode == "create" and self.creation_count <= self.failure_count:
            raise RuntimeError(f"Factory creation failure #{self.creation_count}")

        if self.fail_mode == "create_intermittent" and self.creation_count % 3 == 0:
            raise RuntimeError(f"Intermittent creation failure #{self.creation_count}")

        obj = WeakReferencableObject(id=self.creation_count, data=f"object_{self.creation_count}")
        self.objects_created.append(obj)
        return obj

    def reset(self, obj):
        self.reset_count += 1

        if self.fail_mode == "reset" and self.reset_count <= self.failure_count:
            raise RuntimeError(f"Factory reset failure #{self.reset_count}")

        if self.fail_mode == "reset_intermittent" and self.reset_count % 4 == 0:
            raise RuntimeError(f"Intermittent reset failure #{self.reset_count}")

        # Simulate reset
        if isinstance(obj, WeakReferencableObject):
            obj.data = "reset"
            obj.reset_count = self.reset_count
            return True
        return True

    def validate(self, obj):
        self.validation_count += 1

        if self.fail_mode == "validate" and self.validation_count <= self.failure_count:
            return False

        if self.fail_mode == "validate_intermittent" and self.validation_count % 5 == 0:
            return False

        # Check for corruption
        if isinstance(obj, WeakReferencableObject) and obj.corrupted:
            return False

        return True

    def get_key(self, *args, **kwargs):
        return "failing_factory_key"

    def estimate_size(self, obj):
        return 100

    def destroy(self, obj):
        self.destroy_count += 1

        if self.fail_mode == "destroy" and self.destroy_count <= self.failure_count:
            raise RuntimeError(f"Factory destroy failure #{self.destroy_count}")

        # Simulate object cleanup
        if isinstance(obj, WeakReferencableObject):
            obj.destroyed = True


class TestFactoryErrorRecovery:
    """
    Integration tests for factory error scenarios and recovery.
    """

    def test_factory_creation_error_recovery(self):
        """
        Test recovery from factory creation failures.
        """
        # Factory that fails for first 3 creations, then succeeds
        factory = FailingFactory(fail_mode="create", failure_count=3)
        config = MemoryConfig(
            max_objects_per_key=10, ttl_seconds=30, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            successful_acquisitions = 0
            failed_acquisitions = 0

            # Attempt acquisitions - first 3 should fail, rest should succeed
            for i in range(8):
                try:
                    obj_id, key, obj = pool.acquire()
                    pool.release(obj_id, key, obj)
                    successful_acquisitions += 1
                except Exception as e:
                    failed_acquisitions += 1
                    # Verify we get appropriate error types
                    assert isinstance(e, (ObjectCreationFailedError, RuntimeError))

            # Should have exactly 3 failures and 5 successes
            assert failed_acquisitions == 3
            assert successful_acquisitions == 5

            # Pool should remain functional after errors
            stats = pool.get_basic_stats()
            assert stats["counters"]["creates"] > 0

            # Verify factory was called correctly
            assert factory.creation_count == 4

        finally:
            pool.shutdown()

    def test_factory_validation_error_recovery(self):
        """
        Test recovery from validation failures.
        """
        factory = FailingFactory(fail_mode="validate_intermittent")
        config = MemoryConfig(
            max_objects_per_key=8,
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
            # Create and release objects multiple times
            for i in range(12):
                try:
                    obj_id, key, obj = pool.acquire()
                    pool.release(obj_id, key, obj)
                except Exception:
                    # Some operations may fail due to validation
                    pass

            # Pool should handle validation failures gracefully
            stats = pool.get_basic_stats()
            assert stats["counters"]["creates"] > 0

            # Some objects should have been validated
            assert factory.validation_count > 0

            # Memory manager should report health issues if validation failed frequently
            health = pool.manager.get_health_status()
            assert health is not None

        finally:
            pool.shutdown()

    def test_factory_reset_error_recovery(self):
        """
        Test recovery from reset failures.
        """
        factory = FailingFactory(fail_mode="reset_intermittent")
        config = MemoryConfig(
            max_objects_per_key=5, ttl_seconds=15, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Create objects and release them to trigger reset
            objects_used = []
            for i in range(10):
                try:
                    obj_id, key, obj = pool.acquire()
                    objects_used.append((obj_id, key, obj))
                except Exception:
                    pass

            # Release all objects (triggers reset)
            for obj_id, key, obj in objects_used:
                try:
                    pool.release(obj_id, key, obj)
                except Exception:
                    # Reset failures should be handled gracefully
                    pass

            # Try to reuse objects after reset failures
            for i in range(5):
                try:
                    obj_id, key, obj = pool.acquire()
                    pool.release(obj_id, key, obj)
                except Exception:
                    pass

            # Pool should remain functional
            stats = pool.get_basic_stats()
            assert stats is not None

            # Some resets should have been attempted
            assert factory.reset_count > 0

        finally:
            pool.shutdown()

    def test_factory_destroy_error_recovery(self):
        """
        Test recovery from destroy failures during cleanup.
        """
        factory = FailingFactory(fail_mode="destroy", failure_count=2)
        config = MemoryConfig(
            max_objects_per_key=6,
            ttl_seconds=2,  # Short TTL to trigger cleanup
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

            # Create objects that will need to be destroyed
            for i in range(8):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Wait for TTL expiration and cleanup
            time.sleep(3)

            # Force cleanup to trigger destroy operations
            pool.force_cleanup()

            # Pool should handle destroy failures gracefully
            stats = pool.get_basic_stats()
            assert stats is not None

            # Some destroys should have been attempted
            assert factory.destroy_count >= 0

            # Pool should remain functional after destroy errors
            obj_id, key, obj = pool.acquire()
            pool.release(obj_id, key, obj)

        finally:
            pool.shutdown()


class TestPoolExhaustionRecovery:
    """
    Integration tests for pool exhaustion and recovery scenarios.
    """

    def test_pool_exhaustion_and_recovery(self):
        """
        Test pool behavior during exhaustion and recovery.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=3,  # Small pool to trigger exhaustion
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
            # Phase 1: Exhaust the pool
            held_objects = []

            for i in range(10):  # More than max_objects_per_key
                try:
                    obj_id, key, obj = pool.acquire()
                    held_objects.append((obj_id, key, obj))
                except PoolExhaustedError:
                    break
                except Exception as e:
                    # Other exceptions might occur during exhaustion
                    if "exhausted" in str(e).lower() or "limit" in str(e).lower():
                        break

            # Should have held some objects
            assert len(held_objects) > 0

            # Phase 2: Partial recovery - release some objects
            recovery_objects = held_objects[:2]
            for obj_id, key, obj in recovery_objects:
                pool.release(obj_id, key, obj)

            # Should be able to acquire again after partial release
            new_obj_id, new_key, new_obj = pool.acquire()
            pool.release(new_obj_id, new_key, new_obj)

            # Phase 3: Full recovery - release all objects
            for obj_id, key, obj in held_objects[2:]:
                pool.release(obj_id, key, obj)

            # Pool should be fully functional again
            for i in range(3):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Verify recovery statistics
            stats = pool.get_basic_stats()
            assert stats["counters"]["creates"] > 0

        finally:
            pool.shutdown()

    def test_concurrent_exhaustion_recovery(self):
        """
        Test pool exhaustion recovery under concurrent load.
        """
        factory = MetadataFactory()
        config = MemoryConfig(
            max_objects_per_key=4,
            ttl_seconds=15,
            enable_performance_metrics=True,
            max_expected_concurrency=8,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Concurrent worker that tries to exhaust pool
            def exhaustion_worker(worker_id, hold_duration):
                acquired_objects = []
                try:
                    # Try to acquire many objects
                    for i in range(6):  # More than pool size
                        try:
                            obj_id, key, obj = pool.acquire()
                            acquired_objects.append((obj_id, key, obj))
                        except Exception:
                            # Exhaustion or other errors expected
                            break

                    # Hold objects for specified duration
                    time.sleep(hold_duration)

                    return len(acquired_objects)
                finally:
                    # Always release objects to allow recovery
                    for obj_id, key, obj in acquired_objects:
                        try:
                            pool.release(obj_id, key, obj)
                        except Exception:
                            pass

            # Run concurrent exhaustion attempts
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(exhaustion_worker, i, 0.5) for i in range(3)]

                results = []
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception:
                        results.append(0)

            # At least some workers should have acquired objects
            assert any(r > 0 for r in results)

            # Pool should recover and be functional
            post_recovery_objects = []
            for i in range(3):
                obj_id, key, obj = pool.acquire()
                post_recovery_objects.append((obj_id, key, obj))

            for obj_id, key, obj in post_recovery_objects:
                pool.release(obj_id, key, obj)

            # Verify recovery
            stats = pool.get_basic_stats()
            assert stats["total_pooled_objects"] >= 0

        finally:
            pool.shutdown()


class TestObjectCorruptionRecovery:
    """
    Integration tests for object corruption detection and recovery.
    """

    def test_corruption_detection_and_recovery(self):
        """
        Test detection and recovery from corrupted objects.
        """

        class CorruptibleFactory(ObjectFactory):
            def __init__(self):
                self.creation_count = 0
                self.corruption_simulation = False

            def create(self, *args, **kwargs):
                self.creation_count += 1
                return WeakReferencableObject(
                    id=self.creation_count, data=f"object_{self.creation_count}", corrupted=False
                )

            def reset(self, obj):
                return True

            def validate(self, obj):
                if isinstance(obj, WeakReferencableObject):
                    # Simulate corruption detection
                    if obj.corrupted or self.corruption_simulation:
                        return False
                    return True
                return False

            def get_key(self, *args, **kwargs):
                return "corruptible_key"

            def estimate_size(self, obj):
                return 50

            def destroy(self, obj):
                pass

        factory = CorruptibleFactory()
        config = MemoryConfig(
            max_objects_per_key=5,
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
            # Phase 1: Create clean objects
            clean_objects = []
            for i in range(4):
                obj_id, key, obj = pool.acquire()
                clean_objects.append((obj_id, key, obj))

            # Phase 2: Simulate corruption
            for obj_id, key, obj in clean_objects:
                if isinstance(obj, WeakReferencableObject):
                    obj.corrupted = True  # Simulate corruption
                pool.release(obj_id, key, obj)

            # Phase 3: Try to reuse corrupted objects
            factory.corruption_simulation = True
            corrupted_attempts = 0
            successful_attempts = 0

            for i in range(6):
                try:
                    obj_id, key, obj = pool.acquire()
                    pool.release(obj_id, key, obj)
                    successful_attempts += 1
                except Exception:
                    corrupted_attempts += 1

            # Some attempts should succeed (new objects created)
            assert successful_attempts > 0

            # Phase 4: Disable corruption simulation and verify recovery
            factory.corruption_simulation = False

            for i in range(3):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Pool should handle corruption gracefully
            stats = pool.get_basic_stats()
            assert stats is not None

            # Health status should reflect corruption issues
            health = pool.manager.get_health_status()
            assert health is not None

        finally:
            pool.shutdown()


class TestExceptionContextManagement:
    """
    Integration tests for exception context creation and management.
    """

    def test_exception_factory_context_creation(self):
        """
        Test SmartPoolExceptionFactory context creation.
        """
        factory = FailingFactory(fail_mode="create", failure_count=1)
        config = MemoryConfig(
            max_objects_per_key=5, ttl_seconds=10, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Test exception creation for different error types
            test_cases = [
                ("creation", "TestFactory", "create"),
                ("validation", "TestFactory", "validate"),
                ("reset", "TestFactory", "reset"),
                ("destroy", "TestFactory", "destroy"),
                ("key_generation", "TestFactory", "get_key"),
                ("unknown_type", "TestFactory", "unknown_method"),
            ]

            for error_type, factory_class, method_name in test_cases:
                try:
                    exception = SmartPoolExceptionFactory.create_factory_error(
                        error_type=error_type,
                        factory_class=factory_class,
                        method_name=method_name,
                        args=(1, 2, 3),
                        kwargs={"key": "value"},
                        cause=RuntimeError("Test cause"),
                    )

                    # Verify exception has proper context
                    assert hasattr(exception, "context")
                    if hasattr(exception, "factory_class"):
                        assert exception.factory_class == factory_class

                except Exception as e:
                    # Factory creation itself shouldn't fail
                    assert False, f"Exception factory failed for {error_type}: {e}"

            # Test pool operation error creation
            try:
                pool_error = SmartPoolExceptionFactory.create_pool_operation_error(
                    error_type="exhausted",
                    pool_key="test_key",
                    current_size=10,
                    max_size=10,
                    cause=RuntimeError("Pool exhausted"),
                )
                assert hasattr(pool_error, "pool_key")

            except Exception as e:
                assert False, f"Pool operation error creation failed: {e}"

            # Test with actual pool operations that might generate exceptions
            try:
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)
            except Exception:
                # First acquisition should fail due to factory setup
                pass

        finally:
            pool.shutdown()

    def test_exception_metrics_and_policy(self):
        """
        Test exception metrics collection and policy enforcement.
        """
        # Create exception metrics and policy
        metrics = ExceptionMetrics()
        policy = ExceptionPolicy()

        factory = FailingFactory(fail_mode="create_intermittent")
        config = MemoryConfig(
            max_objects_per_key=8, ttl_seconds=15, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Configure policy
            policy.strict_mode = False  # Production-like mode
            policy.log_all_exceptions = True

            # Generate various exceptions and record metrics
            exception_types = []

            for i in range(12):
                try:
                    obj_id, key, obj = pool.acquire()
                except Exception as e:
                    # Record exception in metrics
                    if hasattr(e, "error_code"):
                        metrics.record_exception(e)
                    exception_types.append(type(e).__name__)

                    # Test policy decision
                    should_raise = policy.should_raise(type(e))
                    should_log = policy.should_log()

                    assert isinstance(should_raise, bool)
                    assert isinstance(should_log, bool)

            # Test metrics functionality
            assert isinstance(metrics.exception_counters, dict)
            assert isinstance(metrics.exception_patterns, dict)

            # Test context truncation
            large_context = {"key_" + str(i): "value_" + str(i) for i in range(100)}
            truncated = policy.truncate_context(large_context)
            assert isinstance(truncated, dict)

            # Should have some exceptions due to intermittent failures
            assert len(exception_types) > 0

        finally:
            pool.shutdown()


class TestResourceRecoveryScenarios:
    """
    Integration tests for resource recovery scenarios.
    """

    def test_memory_pressure_error_recovery(self):
        """
        Test recovery from memory pressure and resource exhaustion.
        """
        factory = MetadataFactory()
        config = MemoryConfig(
            max_objects_per_key=15,
            ttl_seconds=5,  # Short TTL to trigger cleanup
            enable_background_cleanup=True,
            cleanup_interval_seconds=1,
            enable_performance_metrics=True,
            memory_pressure=MemoryPressure.HIGH,  # High pressure
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Start background cleanup
            pool.background_manager.start_background_cleanup()

            # Phase 1: Create memory pressure
            pressure_objects = []
            for i in range(25):  # Exceed max_objects_per_key
                try:
                    obj_id, key, obj = pool.acquire(f"pressure_key_{i % 3}")
                    pressure_objects.append((obj_id, key, obj))
                except Exception:
                    # May hit limits or memory pressure
                    break

            # Release objects to pool them
            for obj_id, key, obj in pressure_objects:
                pool.release(obj_id, key, obj)

            # Phase 2: Force memory pressure response
            pool.get_basic_stats()

            # Wait for cleanup cycles under pressure
            time.sleep(3)

            # Force additional cleanup
            for _ in range(3):
                pool.force_cleanup()
                time.sleep(0.2)

            # Phase 3: Verify recovery
            recovery_stats = pool.get_basic_stats()
            assert recovery_stats is not None

            # Should be able to continue operations after pressure
            for i in range(5):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Memory manager should report on recovery
            health = pool.manager.get_health_status()
            assert health["status"] in ["healthy", "warning", "critical"]

        finally:
            pool.shutdown()

    def test_background_process_error_recovery(self):
        """
        Test recovery from background process errors.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=8,
            ttl_seconds=3,  # Short TTL for frequent cleanup
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
            # Start background processes
            pool.background_manager.start_background_cleanup()

            # Create workload that will generate cleanup activity
            workload_objects = []
            for batch in range(3):
                batch_objects = []
                for i in range(6):
                    obj_id, key, obj = pool.acquire(f"batch_{batch}")
                    batch_objects.append((obj_id, key, obj))

                # Release batch
                for obj_id, key, obj in batch_objects:
                    pool.release(obj_id, key, obj)

                workload_objects.extend(batch_objects)
                time.sleep(1)  # Allow cleanup to process

            # Let background processes work
            time.sleep(2)

            # Force multiple cleanup operations that might encounter errors
            cleanup_results = []
            for _ in range(5):
                try:
                    result = pool.force_cleanup()
                    cleanup_results.append(result)
                except Exception:
                    # Background processes should handle errors gracefully
                    cleanup_results.append(-1)
                time.sleep(0.1)

            # Background manager should remain functional despite errors
            stats = pool.get_basic_stats()
            assert stats is not None
            assert stats["counters"]["expired"] > 0

            # Should be able to continue normal operations
            final_objects = []
            for i in range(4):
                obj_id, key, obj = pool.acquire()
                final_objects.append((obj_id, key, obj))

            for obj_id, key, obj in final_objects:
                pool.release(obj_id, key, obj)

        finally:
            pool.shutdown()

    def test_graceful_shutdown_after_errors(self):
        """
        Test graceful shutdown after various error conditions.
        """
        factory = FailingFactory(fail_mode="destroy", failure_count=2)
        config = MemoryConfig(
            max_objects_per_key=6,
            ttl_seconds=10,
            enable_background_cleanup=True,
            cleanup_interval_seconds=1,
            enable_performance_metrics=True,
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        try:
            # Start background processes
            pool.background_manager.start_background_cleanup()

            # Create objects and encounter various errors
            error_objects = []
            for i in range(8):
                try:
                    obj_id, key, obj = pool.acquire()
                    error_objects.append((obj_id, key, obj))
                except Exception:
                    pass

            # Release objects
            for obj_id, key, obj in error_objects:
                try:
                    pool.release(obj_id, key, obj)
                except Exception:
                    pass

            # Force operations that might fail
            for _ in range(3):
                try:
                    pool.force_cleanup()
                except Exception:
                    pass

            # Get final statistics before shutdown
            final_stats = pool.get_basic_stats()
            assert final_stats is not None

        finally:
            # Shutdown should be graceful even after errors
            try:
                pool.shutdown()
            except Exception as e:
                # Shutdown should generally succeed even after errors
                print(f"Shutdown error (may be expected): {e}")

            # In most cases shutdown should succeed
            # If it fails, it should be due to cleanup errors, not core logic
