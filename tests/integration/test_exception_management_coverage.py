"""
Integration tests specifically targeting uncovered lines in exception management modules.
Focuses on factory_creating_exceptions_context.py and management_utils.py coverage.
"""

import time

from examples.factories import BytesIOFactory, MetadataFactory
from smartpool import SmartObjectManager
from smartpool.config import MemoryConfig, PoolConfiguration
from smartpool.core.exceptions import (
    AcquisitionTimeoutError,
    ExceptionMetrics,
    ExceptionPolicy,
    FactoryCreationError,
    FactoryDestroyError,
    FactoryError,
    FactoryKeyGenerationError,
    FactoryResetError,
    FactoryValidationError,
    HighLatencyError,
    LowHitRateError,
    ObjectAcquisitionError,
    ObjectCorruptionError,
    ObjectCreationFailedError,
    ObjectReleaseError,
    ObjectStateCorruptedError,
    PoolExhaustedError,
    PoolOperationError,
    SmartPoolError,
    SmartPoolExceptionFactory,
)
from smartpool.core.factory_interface import ObjectFactory
from tests.testing_utils import WeakReferencableObject


class TestSmartPoolExceptionFactoryEdgeCases:
    """
    Integration tests targeting uncovered lines in SmartPoolExceptionFactory.
    """

    def test_all_factory_error_types_creation(self):
        """
        Test creation of all factory error types to cover switch branches.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(
            max_objects_per_key=5, ttl_seconds=10, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Test all factory error types
            error_test_cases = [
                {
                    "error_type": "creation",
                    "factory_class": "TestFactory",
                    "method_name": "create",
                    "expected_type": FactoryCreationError,
                    "context": {"args": (1, 2, 3), "kwargs": {"size": 1024}},
                },
                {
                    "error_type": "validation",
                    "factory_class": "TestFactory",
                    "method_name": "validate",
                    "expected_type": FactoryValidationError,
                    "context": {"attempts": 3, "max_attempts": 5},
                },
                {
                    "error_type": "reset",
                    "factory_class": "TestFactory",
                    "method_name": "reset",
                    "expected_type": FactoryResetError,
                    "context": {"object_type": "dict"},
                },
                {
                    "error_type": "destroy",
                    "factory_class": "TestFactory",
                    "method_name": "destroy",
                    "expected_type": FactoryDestroyError,
                    "context": {"object_type": "BytesIO"},
                },
                {
                    "error_type": "key_generation",
                    "factory_class": "TestFactory",
                    "method_name": "get_key",
                    "expected_type": FactoryKeyGenerationError,
                    "context": {"args": ("arg1", "arg2"), "kwargs": {"param": "value"}},
                },
                {
                    "error_type": "unknown_error_type",
                    "factory_class": "TestFactory",
                    "method_name": "unknown_method",
                    "expected_type": FactoryError,
                    "context": {"custom_context": "test_value"},
                },
            ]

            for case in error_test_cases:
                # Test without cause
                exception = SmartPoolExceptionFactory.create_factory_error(
                    error_type=case["error_type"],
                    factory_class=case["factory_class"],
                    method_name=case["method_name"],
                    **case["context"],
                )

                assert isinstance(exception, case["expected_type"])
                if hasattr(exception, "factory_class"):
                    assert exception.factory_class == case["factory_class"]

                # Test with message parameter
                exception_with_message = SmartPoolExceptionFactory.create_factory_error(
                    error_type=case["error_type"],
                    factory_class=case["factory_class"],
                    method_name=case["method_name"],
                    message=f"Custom message for {case['error_type']}",
                    **case["context"],
                )

                assert isinstance(exception_with_message, case["expected_type"])

                # Test with cause
                test_cause = RuntimeError(f"Test cause for {case['error_type']}")
                exception_with_cause = SmartPoolExceptionFactory.create_factory_error(
                    error_type=case["error_type"],
                    factory_class=case["factory_class"],
                    method_name=case["method_name"],
                    cause=test_cause,
                    **case["context"],
                )

                assert isinstance(exception_with_cause, case["expected_type"])
                if hasattr(exception_with_cause, "cause"):
                    assert exception_with_cause.cause == test_cause

            # Test integration with actual pool operations
            obj_id, key, obj = pool.acquire()
            pool.release(obj_id, key, obj)

        finally:
            pool.shutdown()

    def test_pool_operation_error_types_creation(self):
        """
        Test creation of all pool operation error types.
        """
        factory = MetadataFactory()
        config = MemoryConfig(max_objects_per_key=3, ttl_seconds=5, enable_performance_metrics=True)

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Test pool operation error types
            pool_error_cases = [
                {
                    "error_type": "exhausted",
                    "pool_key": "test_key",
                    "expected_type": PoolExhaustedError,
                    "context": {"current_size": 10, "max_size": 10, "active_objects_count": 8},
                },
                {
                    "error_type": "acquisition_failed",
                    "pool_key": "test_key",
                    "expected_type": ObjectAcquisitionError,
                    "context": {"timeout_seconds": 30, "attempts": 3},
                },
                {
                    "error_type": "release_failed",
                    "pool_key": "test_key",
                    "expected_type": ObjectReleaseError,
                    "context": {"object_id": "obj_123", "reason": "validation_failed"},
                },
                {
                    "error_type": "timeout",
                    "pool_key": "test_key",
                    "expected_type": AcquisitionTimeoutError,
                    "context": {"timeout_seconds": 10, "wait_time": 12},
                },
                {
                    "error_type": "creation_failed",
                    "pool_key": "test_key",
                    "expected_type": ObjectCreationFailedError,
                    "context": {"factory_class": "TestFactory", "attempts": 2},
                },
                {
                    "error_type": "corruption",
                    "pool_key": "test_key",
                    "expected_type": ObjectCorruptionError,
                    "context": {"object_id": "obj_456", "validation_result": False},
                },
                {
                    "error_type": "unknown_pool_error",
                    "pool_key": "test_key",
                    "expected_type": PoolOperationError,
                    "context": {"custom_field": "test_value"},
                },
            ]

            for case in pool_error_cases:
                # Test without cause
                exception = SmartPoolExceptionFactory.create_pool_operation_error(
                    error_type=case["error_type"], pool_key=case["pool_key"], **case["context"]
                )

                assert isinstance(exception, case["expected_type"])
                if hasattr(exception, "pool_key"):
                    assert exception.pool_key == case["pool_key"]

                # Test with cause
                test_cause = RuntimeError(f"Test cause for {case['error_type']}")
                exception_with_cause = SmartPoolExceptionFactory.create_pool_operation_error(
                    error_type=case["error_type"],
                    pool_key=case["pool_key"],
                    cause=test_cause,
                    **case["context"],
                )

                assert isinstance(exception_with_cause, case["expected_type"])
                if hasattr(exception_with_cause, "cause"):
                    assert exception_with_cause.cause == test_cause

            # Test integration with actual pool operations
            for i in range(4):  # Exceed max_objects_per_key
                try:
                    obj_id, key, obj = pool.acquire()
                    pool.release(obj_id, key, obj)
                except Exception:
                    # May trigger pool operation errors
                    pass

        finally:
            pool.shutdown()


class TestExceptionMetricsComprehensive:
    """
    Integration tests for ExceptionMetrics covering all methods and edge cases.
    """

    def test_exception_metrics_record_and_analyze(self):
        """
        Test comprehensive exception metrics recording and analysis.
        """
        metrics = ExceptionMetrics()

        # Create various SmartPool exceptions to record
        test_exceptions = [
            SmartPoolError("Test error 1", error_code="TEST_001"),
            SmartPoolError("Test error 2", error_code="TEST_002"),
            SmartPoolError("Test error 1 again", error_code="TEST_001"),
            FactoryCreationError("TestFactory", args=(1,), kwargs_dict={"size": 100}),
            FactoryValidationError("TestFactory", validation_attempts=3, max_attempts=5),
            ObjectStateCorruptedError("test_key", object_id="obj_123"),
            HighLatencyError(operation="acquire", actual_latency_ms=500, threshold_ms=100),
            LowHitRateError(hit_rate=0.3, threshold=0.8, hits=30, misses=70, pool_key="test_key"),
        ]

        # Record all exceptions
        for exception in test_exceptions:
            metrics.record_exception(exception)
            time.sleep(0.01)  # Small delay for timing patterns

        # Test counter functionality
        assert metrics.exception_counters["TEST_001"] == 2
        assert metrics.exception_counters["TEST_002"] == 1

        # Test exception pattern recording
        assert len(metrics.exception_patterns) > 0

        # Test error rate tracking
        assert len(metrics.error_rates) > 0

        # Test cleanup functionality by waiting and recording more
        time.sleep(0.1)

        # Record more exceptions to test pattern analysis
        for i in range(5):
            metrics.record_exception(SmartPoolError(f"Batch error {i}", error_code="BATCH_001"))
            time.sleep(0.002)

        # Test that patterns are being tracked
        pattern_keys = list(metrics.exception_patterns.keys())
        assert len(pattern_keys) > 0

        # Test cleanup behavior (simulate time passage)
        metrics.last_cleanup = time.time() - 3600  # 1 hour ago

        # Record another exception to trigger potential cleanup
        metrics.record_exception(SmartPoolError("Cleanup trigger", error_code="CLEANUP_001"))

        # Verify metrics are still functional
        assert metrics.exception_counters["CLEANUP_001"] == 1

    def test_exception_metrics_with_pool_integration(self):
        """
        Test exception metrics integration with actual pool operations.
        """
        metrics = ExceptionMetrics()

        class MetricsTrackingFactory(ObjectFactory):
            def __init__(self, metrics):
                self.metrics = metrics
                self.creation_count = 0
                self.should_fail = False

            def create(self, *args, **kwargs):
                self.creation_count += 1
                if self.should_fail and self.creation_count % 3 == 0:
                    error = FactoryCreationError("MetricsTrackingFactory")
                    self.metrics.record_exception(error)
                    raise RuntimeError("Simulated factory failure")
                return WeakReferencableObject(
                    id=self.creation_count, data=f"object_{self.creation_count}"
                )

            def reset(self, obj):
                return True

            def validate(self, obj):
                return isinstance(obj, WeakReferencableObject)

            def get_key(self, *args, **kwargs):
                return "metrics_test_key"

            def estimate_size(self, obj):
                return 100

            def destroy(self, obj):
                pass

        factory = MetricsTrackingFactory(metrics)
        config = MemoryConfig(
            max_objects_per_key=8, ttl_seconds=15, enable_performance_metrics=True
        )

        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Phase 1: Normal operations
            for i in range(5):
                obj_id, key, obj = pool.acquire()
                pool.release(obj_id, key, obj)

            # Phase 2: Enable failures and track exceptions
            factory.should_fail = True

            successful_ops = 0
            failed_ops = 0

            for i in range(10):
                try:
                    obj_id, key, obj = pool.acquire()
                    successful_ops += 1
                except Exception as e:
                    # Record exceptions that occur during pool operations
                    if hasattr(e, "error_code"):
                        metrics.record_exception(e)
                    failed_ops += 1

            # Should have both successes and failures
            assert successful_ops > 0
            assert failed_ops > 0

            # Metrics should have recorded some exceptions
            assert len(metrics.exception_counters) > 0

        finally:
            pool.shutdown()


class TestExceptionPolicyComprehensive:
    """
    Integration tests for ExceptionPolicy covering all decision paths.
    """

    def test_exception_policy_strict_vs_production_mode(self):
        """
        Test exception policy behavior in strict vs production modes.
        """
        policy_strict = ExceptionPolicy()
        policy_strict.strict_mode = True

        policy_production = ExceptionPolicy()
        policy_production.strict_mode = False

        # Test exceptions that should behave differently in each mode
        test_exception_types = [
            FactoryValidationError,  # Should be recoverable in production
            ObjectCorruptionError,  # Should be recoverable in production
            HighLatencyError,  # Should be recoverable in production
            LowHitRateError,  # Should be recoverable in production
            FactoryCreationError,  # Should raise in both modes
            ObjectCreationFailedError,  # Should raise in both modes
        ]

        for exception_type in test_exception_types:
            strict_decision = policy_strict.should_raise(exception_type)
            production_decision = policy_production.should_raise(exception_type)

            # In strict mode, everything should raise
            assert strict_decision is True

            # In production mode, some should be recoverable
            assert isinstance(production_decision, bool)

            # Both policies should log by default
            assert policy_strict.should_log() is True
            assert policy_production.should_log() is True

    def test_exception_policy_context_truncation(self):
        """
        Test context truncation for large exception contexts.
        """
        policy = ExceptionPolicy()
        policy.max_error_details = 100  # Small limit for testing

        # Create small context (should not be truncated)
        small_context = {"key1": "value1", "key2": "value2"}
        truncated_small = policy.truncate_context(small_context)

        assert truncated_small == small_context
        assert "_truncated" not in truncated_small

        # Create large context (should be truncated)
        large_context = {}
        for i in range(50):
            large_context[f"key_{i}"] = f"very_long_value_{i}" * 10

        truncated_large = policy.truncate_context(large_context)

        # Should be truncated
        assert "_truncated" in truncated_large
        assert "_original_size" in truncated_large
        assert truncated_large["_truncated"] is True
        assert isinstance(truncated_large["_original_size"], int)

        # Should preserve important keys if they exist
        important_context = {
            "pool_key": "important_pool",
            "factory_class": "ImportantFactory",
            "error_type": "critical",
            "operation": "test_operation",
        }
        for i in range(50):
            important_context[f"unimportant_{i}"] = f"long_value_{i}" * 20

        truncated_important = policy.truncate_context(important_context)

        # Important keys should be preserved
        assert "pool_key" in truncated_important
        assert "factory_class" in truncated_important
        assert "error_type" in truncated_important
        assert "operation" in truncated_important
        assert truncated_important["pool_key"] == "important_pool"

    def test_exception_policy_with_pool_integration(self):
        """
        Test exception policy integration with actual pool operations.
        """

        class PolicyEnforcingFactory(ObjectFactory):
            def __init__(self, policy):
                self.policy = policy
                self.creation_count = 0
                self.validation_failures = 0

            def create(self, *args, **kwargs):
                self.creation_count += 1
                if self.creation_count > 10:
                    # Simulate factory exhaustion
                    error = FactoryCreationError("PolicyEnforcingFactory")
                    if self.policy.should_raise(type(error)):
                        raise RuntimeError("Factory exhausted")
                return WeakReferencableObject(
                    id=self.creation_count, data=f"object_{self.creation_count}"
                )

            def reset(self, obj):
                return True

            def validate(self, obj):
                if not isinstance(obj, WeakReferencableObject):
                    self.validation_failures += 1
                    error = FactoryValidationError("PolicyEnforcingFactory")
                    if self.policy.should_raise(type(error)):
                        return False
                return True

            def get_key(self, *args, **kwargs):
                return "policy_test_key"

            def estimate_size(self, obj):
                return 50

            def destroy(self, obj):
                pass

        # Test with strict policy
        strict_policy = ExceptionPolicy()
        strict_policy.strict_mode = True

        factory_strict = PolicyEnforcingFactory(strict_policy)
        pool_strict = SmartObjectManager(
            factory=factory_strict,
            default_config=MemoryConfig(max_objects_per_key=5, ttl_seconds=10),
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Should work normally until limit
            for i in range(8):
                obj_id, key, obj = pool_strict.acquire()
                pool_strict.release(obj_id, key, obj)

            # Test with production policy
            production_policy = ExceptionPolicy()
            production_policy.strict_mode = False

            factory_production = PolicyEnforcingFactory(production_policy)
            pool_production = SmartObjectManager(
                factory=factory_production,
                default_config=MemoryConfig(max_objects_per_key=5, ttl_seconds=10),
                pool_config=PoolConfiguration(register_atexit=False),
            )

            try:
                # Should handle errors more gracefully
                for i in range(8):
                    obj_id, key, obj = pool_production.acquire()
                    pool_production.release(obj_id, key, obj)

                # Both pools should remain functional
                assert pool_strict.get_basic_stats() is not None
                assert pool_production.get_basic_stats() is not None

            finally:
                pool_production.shutdown()

        finally:
            pool_strict.shutdown()


class TestIntegratedErrorScenarios:
    """
    Integration tests combining exception factory, metrics, and policy.
    """

    def test_comprehensive_error_handling_integration(self):
        """
        Test complete error handling pipeline with all components.
        """
        # Set up error handling components
        metrics = ExceptionMetrics()
        policy = ExceptionPolicy()
        policy.strict_mode = False
        policy.performance_monitoring = True

        class ComprehensiveErrorFactory(ObjectFactory):
            def __init__(self, metrics, policy):
                self.metrics = metrics
                self.policy = policy
                self.operation_count = 0
                self.error_scenarios = [
                    "create_failure",
                    "validate_failure",
                    "reset_failure",
                    "destroy_failure",
                    "key_generation_failure",
                ]
                self.current_scenario = 0

            def create(self, *args, **kwargs):
                self.operation_count += 1

                if self.operation_count % 8 == 0:  # Every 8th operation
                    scenario = self.error_scenarios[
                        self.current_scenario % len(self.error_scenarios)
                    ]
                    self.current_scenario += 1

                    if scenario == "create_failure":
                        error = SmartPoolExceptionFactory.create_factory_error(
                            error_type="creation",
                            factory_class="ComprehensiveErrorFactory",
                            method_name="create",
                            args=args,
                            kwargs=kwargs,
                            cause=RuntimeError("Simulated creation failure"),
                        )
                        self.metrics.record_exception(error)

                        if self.policy.should_raise(type(error)):
                            raise RuntimeError(
                                f"Creation failure at operation {self.operation_count}"
                            )
                        else:
                            # Allow creation to proceed if policy doesn't raise
                            pass

                return WeakReferencableObject(
                    id=self.operation_count, data=f"object_{self.operation_count}"
                )

            def reset(self, obj):
                if self.operation_count % 12 == 0:  # Every 12th operation
                    error = SmartPoolExceptionFactory.create_factory_error(
                        error_type="reset",
                        factory_class="ComprehensiveErrorFactory",
                        method_name="reset",
                        object_type=type(obj).__name__,
                        cause=RuntimeError("Simulated reset failure"),
                    )
                    self.metrics.record_exception(error)

                    if self.policy.should_raise(type(error)):
                        return False

                return True

            def validate(self, obj):
                if self.operation_count % 10 == 0:  # Every 10th operation
                    error = SmartPoolExceptionFactory.create_factory_error(
                        error_type="validation",
                        factory_class="ComprehensiveErrorFactory",
                        method_name="validate",
                        attempts=1,
                        max_attempts=1,
                        cause=RuntimeError("Simulated validation failure"),
                    )
                    self.metrics.record_exception(error)

                    if self.policy.should_raise(type(error)):
                        return False

                return isinstance(obj, WeakReferencableObject)

            def get_key(self, *args, **kwargs):
                return "comprehensive_test_key"

            def estimate_size(self, obj):
                return 75

            def destroy(self, obj):
                if self.operation_count % 15 == 0:  # Every 15th operation
                    error = SmartPoolExceptionFactory.create_factory_error(
                        error_type="destroy",
                        factory_class="ComprehensiveErrorFactory",
                        method_name="destroy",
                        object_type=type(obj).__name__,
                        cause=RuntimeError("Simulated destroy failure"),
                    )
                    self.metrics.record_exception(error)

                    if self.policy.should_raise(type(error)):
                        raise RuntimeError("Destroy failure")

        factory = ComprehensiveErrorFactory(metrics, policy)
        config = MemoryConfig(
            max_objects_per_key=10,
            ttl_seconds=5,
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
            # Start background cleanup to trigger destroy operations
            pool.background_manager.start_background_cleanup()

            # Run operations that will trigger various error scenarios
            successful_operations = 0
            failed_operations = 0

            for i in range(25):
                try:
                    obj_id, key, obj = pool.acquire()
                    successful_operations += 1
                except Exception as e:
                    failed_operations += 1
                    # Record any pool-level exceptions
                    if hasattr(e, "error_code"):
                        metrics.record_exception(e)

                time.sleep(0.05)  # Small delay for background operations

            # Wait for background cleanup to potentially trigger destroy errors
            time.sleep(2)

            # Force cleanup to trigger more destroy operations
            for _ in range(3):
                try:
                    pool.force_cleanup()
                except Exception:
                    # Cleanup errors should be handled gracefully
                    pass
                time.sleep(0.1)

            # Verify that error handling pipeline worked
            assert successful_operations > 0

            # Metrics should have recorded various exception types
            assert len(metrics.exception_counters) > 0

            # Policy should have made some decisions
            test_exceptions = [
                FactoryValidationError("TestFactory"),
                ObjectCorruptionError("test_key", corruption_count=1, threshold=1),
                HighLatencyError(operation="acquire", actual_latency_ms=500, threshold_ms=100),
            ]

            for exc in test_exceptions:
                should_raise = policy.should_raise(type(exc))
                should_log = policy.should_log()
                assert isinstance(should_raise, bool)
                assert isinstance(should_log, bool)

            # Pool should remain functional despite errors
            final_stats = pool.get_basic_stats()
            assert final_stats is not None

        finally:
            pool.shutdown()
