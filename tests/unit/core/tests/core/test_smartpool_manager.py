"""
Tests for the SmartObjectManager, covering its orchestration, configuration,
context management, acquire/release operations, feature toggles, cleanup,
statistics, and error handling.
"""

import logging
import time
from collections import deque
from unittest.mock import Mock, patch

import pytest

import smartpool.core.smartpool_manager as som_module
from smartpool.config import (
    MemoryConfig,
    MemoryPreset,
    MetricsMode,
    MetricsOverloadPolicy,
    PoolConfiguration,
)
from smartpool.core.exceptions.operation_error import (
    ObjectAcquisitionError,
    ObjectCreationFailedError,
    ObjectStateCorruptedError,
)
from smartpool.core.factory_interface import ObjectFactory, ObjectState
from smartpool.core.smartpool_manager import (
    PoolContext,
    PooledObject,
    SmartObjectManager,
)
from smartpool.core.utils import safe_log

# pylint: disable=W0201,W0212,C0302


class MockFactory(ObjectFactory):
    """Mock factory for testing purposes."""

    def create(self, *args, **kwargs):
        return Mock()

    def reset(self, obj):
        return True

    def validate(self, obj):
        return True

    def get_key(self, *args, **kwargs):
        return "test_key"

    def estimate_size(self, obj):
        return 100

    def destroy(self, obj):
        pass


def patch_memory_managers():
    """
    Helper to patch all managers of the pool for orchestration testing.
    Patches the managers where they are imported in the smartpool_manager module.
    """
    # Patch the imported classes directly on the module
    active_patcher = patch.object(som_module, "ActiveObjectsManager", autospec=True)
    operations_patcher = patch.object(som_module, "PoolOperationsManager", autospec=True)
    manager_patcher = patch.object(som_module, "MemoryManager", autospec=True)
    optimizer_patcher = patch.object(som_module, "MemoryOptimizer", autospec=True)
    background_patcher = patch.object(som_module, "BackgroundManager", autospec=True)

    mock_active = active_patcher.start()
    mock_operations = operations_patcher.start()
    mock_manager = manager_patcher.start()
    mock_optimizer = optimizer_patcher.start()
    mock_background = background_patcher.start()

    class MockManagerContext:
        """Context manager for patching memory managers."""

        def __enter__(self):
            return {
                "active": mock_active,
                "operations": mock_operations,
                "manager": mock_manager,
                "optimizer": mock_optimizer,
                "background": mock_background,
            }

        def __exit__(self, exc_type, exc_val, exc_tb):
            active_patcher.stop()
            operations_patcher.stop()
            manager_patcher.stop()
            optimizer_patcher.stop()
            background_patcher.stop()

    return MockManagerContext()


class TestSmartObjectManagerOrchestration:
    """
    Tests for SmartObjectManager focusing on its role as an orchestrator.
    It verifies that the pool correctly delegates tasks to its specialized managers.
    """

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = MockFactory()

    def test_initialization_delegates_to_managers(self):
        """Test that the pool initializes all its managers."""
        with patch_memory_managers() as mocks:
            mock_active_objects_manager = mocks["active"]
            mock_pool_operations_manager = mocks["operations"]
            mock_memory_manager = mocks["manager"]
            mock_memory_optimizer = mocks["optimizer"]
            mock_background_manager = mocks["background"]

            pool = SmartObjectManager(
                factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
            )

            # The mocks should have been called during initialization
            mock_active_objects_manager.assert_called_once_with(pool)
            mock_pool_operations_manager.assert_called_once_with(pool)
            mock_memory_manager.assert_called_once_with(pool)
            mock_memory_optimizer.assert_called_once_with(pool)
            mock_background_manager.assert_called_once_with(pool)

            pool.shutdown()

    def test_acquire_delegates_correctly(self):
        """Test that acquire() delegates its operations to the correct managers."""
        with patch_memory_managers():  # Remove unused variable
            pool = SmartObjectManager(
                factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
            )

            # Access the actual mock instances that were created
            operations_mock = pool.operations_manager  # pylint: disable=no-member
            active_mock = pool.active_manager  # pylint: disable=no-member

            # Simulate a pool miss
            operations_mock.find_valid_object_with_retry.return_value = Mock(success=False)
            active_mock.track_active_object.return_value = 123  # Mock object ID

            obj_id, key, _ = pool.acquire()

            # Verify delegation chain for acquire
            # pylint: disable=no-member
            operations_mock.update_key_access.assert_called_once()
            operations_mock.find_valid_object_with_retry.assert_called_once()
            active_mock.track_active_object.assert_called_once()
            # pylint: enable=no-member
            assert obj_id == 123
            assert key == "test_key"

            pool.shutdown()

    def test_release_delegates_correctly(self):
        """Test that release() delegates its operations to the correct managers."""
        with patch_memory_managers():  # Remove unused variable
            pool = SmartObjectManager(
                factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
            )

            # Access the actual mock instances that were created
            operations_mock = pool.operations_manager  # pylint: disable=no-member
            active_mock = pool.active_manager  # pylint: disable=no-member

            mock_obj = Mock()

            # Simulate object that can be returned to the pool
            operations_mock.validate_and_reset_object.return_value = True
            operations_mock.should_add_to_pool.return_value = True

            pool.release(123, "test_key", mock_obj)

            # Verify delegation chain for release
            # pylint: disable=no-member
            active_mock.untrack_active_object.assert_called_once_with(123)
            operations_mock.validate_and_reset_object.assert_called_once_with(
                mock_obj, "test_key", pool.default_config
            )
            operations_mock.should_add_to_pool.assert_called_once()
            operations_mock.add_to_pool.assert_called_once()
            # pylint: enable=no-member

            pool.shutdown()

    def test_high_level_methods_delegate_to_memory_manager(self):
        """Test that high-level management methods delegate to MemoryManager."""
        with patch_memory_managers():  # Remove unused variable
            pool = SmartObjectManager(
                factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
            )

            # Access the actual mock instance that was created
            manager_mock = pool.manager  # pylint: disable=no-member

            pool.get_detailed_stats()
            # pylint: disable=no-member
            manager_mock.get_detailed_stats.assert_called_once()

            pool.get_performance_report()
            manager_mock.get_performance_report.assert_called_once()

            pool.get_health_status()
            manager_mock.get_health_status.assert_called_once()
            # pylint: enable=no-member

            pool.shutdown()

    def test_get_preset_info_delegates_to_manager(self):
        """Test that get_preset_info() delegates to MemoryManager."""
        with patch_memory_managers():  # Remove unused variable
            pool = SmartObjectManager(
                factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
            )

            # Access the actual mock instance and set up return value
            manager_mock = pool.manager  # pylint: disable=no-member
            expected_info = {"preset": "CUSTOM", "details": "test"}
            manager_mock.get_preset_info.return_value = expected_info

            result = pool.get_preset_info()

            manager_mock.get_preset_info.assert_called_once()  # pylint: disable=no-member
            assert result == expected_info

            pool.shutdown()

    def test_switch_preset_delegates_to_manager(self):
        """Test that switch_preset() delegates to MemoryManager."""
        with patch_memory_managers():  # Remove unused variable
            pool = SmartObjectManager(
                factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
            )

            # Access the actual mock instance and set up return value
            manager_mock = pool.manager  # pylint: disable=no-member
            expected_result = {
                "success": True,
                "old_preset": "CUSTOM",
                "new_preset": "HIGH_THROUGHPUT",
            }
            manager_mock.switch_preset.return_value = expected_result

            new_preset = MemoryPreset.HIGH_THROUGHPUT
            result = pool.switch_preset(new_preset)

            # pylint: disable=no-member
            manager_mock.switch_preset.assert_called_once_with(new_preset)
            # pylint: enable=no-member
            assert result == expected_result

            pool.shutdown()

    def test_shutdown_delegates_to_managers(self):
        """Test that shutdown() is cascaded to relevant managers."""
        with patch_memory_managers():  # Remove unused variable
            pool = SmartObjectManager(
                factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
            )

            # Access the actual mock instances that were created
            background_mock = pool.background_manager  # pylint: disable=no-member
            operations_mock = pool.operations_manager  # pylint: disable=no-member
            active_mock = pool.active_manager  # pylint: disable=no-member

            pool.shutdown()

            # pylint: disable=no-member
            background_mock.shutdown.assert_called_once()
            operations_mock.clear_all_data.assert_called_once()
            active_mock.clear_all.assert_called_once()
            # pylint: enable=no-member


class TestSmartObjectManagerConfiguration:
    """Tests for SmartObjectManager configuration and initialization."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = MockFactory()

    def test_config_initialization_with_preset_and_override(self):
        """Test configuration initialization with preset and override parameters."""
        # Test with preset and custom default_config that has non-default values
        custom_config = MemoryConfig()
        custom_config.max_pool_size = 50  # Non-default value
        custom_config.enable_logging = False  # Non-default value

        pool = SmartObjectManager(
            factory=self.factory,
            default_config=custom_config,
            preset=MemoryPreset.HIGH_THROUGHPUT,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        # Verify preset was applied and then overridden
        assert pool.current_preset == MemoryPreset.HIGH_THROUGHPUT
        assert pool.default_config.max_pool_size == 50  # Should be overridden
        assert pool.default_config.enable_logging is False  # Should be overridden

        pool.shutdown()

    def test_config_initialization_no_preset_with_default_config(self):
        """Test configuration initialization without preset but with default_config."""
        custom_config = MemoryConfig()
        custom_config.max_pool_size = 75

        pool = SmartObjectManager(
            factory=self.factory,
            default_config=custom_config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        assert pool.current_preset == MemoryPreset.CUSTOM
        assert pool.default_config.max_pool_size == 75

        pool.shutdown()

    def test_config_initialization_no_preset_no_default_config(self):
        """Test configuration initialization without preset and without default_config."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        assert pool.current_preset == MemoryPreset.CUSTOM
        assert isinstance(pool.default_config, MemoryConfig)

        pool.shutdown()

    def test_multiple_key_configurations(self):
        """Test setting and getting configurations for multiple keys."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        config1 = MemoryConfig()
        config1.max_pool_size = 10

        config2 = MemoryConfig()
        config2.max_pool_size = 20

        pool.set_config_for_key("key1", config1)
        pool.set_config_for_key("key2", config2)

        assert pool.get_config_for_key("key1").max_pool_size == 10
        assert pool.get_config_for_key("key2").max_pool_size == 20
        assert pool.get_config_for_key("key3") == pool.default_config  # Default for unknown key

        pool.shutdown()

    def test_background_cleanup_disabled(self):
        """Test initialization when background cleanup is disabled."""
        config = MemoryConfig()
        config.enable_background_cleanup = False

        pool = SmartObjectManager(
            factory=self.factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        # Background manager should still exist but not start cleanup
        assert pool.background_manager is not None

        pool.shutdown()

    def test_atexit_registration_disabled(self):
        """Test initialization when atexit registration is disabled."""
        with patch("smartpool.core.smartpool_manager.atexit.register") as mock_register:
            pool = SmartObjectManager(
                factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
            )
            mock_register.assert_not_called()
            pool.shutdown()

    def test_atexit_registration_enabled(self):
        """Test initialization when atexit registration is enabled."""
        with patch("smartpool.core.smartpool_manager.atexit.register") as mock_register:
            pool = SmartObjectManager(
                factory=self.factory, pool_config=PoolConfiguration(register_atexit=True)
            )
            mock_register.assert_called_once()
            pool.shutdown()


class TestSmartObjectManagerContextManagement:
    """Tests for SmartObjectManager context management features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = MockFactory()

    def test_acquire_context_manager(self):
        """Test the acquire_context context manager."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        # Test successful context usage
        with pool.acquire_context() as obj:
            assert obj is not None

        pool.shutdown()

    def test_pool_context_manual_usage(self):
        """Test PoolContext used manually (not with 'with' statement)."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        context = PoolContext(pool)
        obj = context.__enter__()  # pylint: disable=C2801
        assert obj is not None

        # Test exit with no exception
        context.__exit__(None, None, None)

        pool.shutdown()

    def test_pool_context_with_exception(self):
        """Test PoolContext when exception occurs."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        try:
            with pool.acquire_context() as obj:
                assert obj is not None
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected

        pool.shutdown()

    def test_pool_context_with_invalid_state(self):
        """Test PoolContext.__exit__ when obj_id, key, or obj is None."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        context = PoolContext(pool)
        # Don't call __enter__, so obj_id, key, obj remain None
        context.__exit__(None, None, None)  # Should not raise exception

        pool.shutdown()

    def test_pool_context_enter_with_none_object(self):
        """Test PoolContext.__enter__ when pool.acquire returns None as object."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        # Mock the acquire method to return None as the object
        with patch.object(pool, "acquire") as mock_acquire:
            # Configure the mock to return (obj_id, key, None)
            mock_acquire.return_value = (1, "test_key", None)

            context = PoolContext(pool, "test_arg")

            # Verify that ObjectAcquisitionError is raised with the expected message
            with pytest.raises(ObjectAcquisitionError, match="Failed to acquire object from pool"):
                context.__enter__()  # pylint: disable=C2801

            # Verify that acquire was called with the right arguments
            mock_acquire.assert_called_once_with("test_arg")

            # Verify that obj_id, key are set but obj is None
            assert context.obj_id == 1
            assert context.key == "test_key"
            assert context.obj is None

        pool.shutdown()

    def test_pool_context_enter_with_various_none_scenarios(self):
        """Test PoolContext.__enter__ with different None scenarios."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        test_cases = [
            # (obj_id, key, obj, should_raise)
            (1, "test_key", None, True),  # obj is None
            (None, "test_key", None, True),  # obj_id and obj are None
            (1, None, None, True),  # key and obj are None
            (None, None, None, True),  # Everything is None
        ]

        for obj_id, key, obj, should_raise in test_cases:
            with patch.object(pool, "acquire") as mock_acquire:
                mock_acquire.return_value = (obj_id, key, obj)

                context = PoolContext(pool)

                if should_raise:
                    with pytest.raises(
                        ObjectAcquisitionError, match="Failed to acquire object from pool"
                    ):
                        context.__enter__()  # pylint: disable=C2801

                    # Verify the state after failed enter
                    assert context.obj_id == obj_id
                    assert context.key == key
                    assert context.obj is None
                else:
                    # This case shouldn't happen in practice, but testing for completeness
                    result = context.__enter__()  # pylint: disable=C2801
                    assert result == obj

        pool.shutdown()

    def test_pool_context_exit_after_failed_enter(self):
        """Test PoolContext.__exit__ behavior after a failed __enter__."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with (
            patch.object(pool, "acquire") as mock_acquire,
            patch.object(pool, "release") as mock_release,
        ):
            # Mock acquire to return None object
            mock_acquire.return_value = (1, "test_key", None)

            context = PoolContext(pool)

            # Enter should fail
            with pytest.raises(ObjectAcquisitionError, match="Failed to acquire object from pool"):
                context.__enter__()  # pylint: disable=C2801

            # Even though enter failed, exit should handle it gracefully
            # Since obj is None, release should NOT be called
            context.__exit__(None, None, None)

            # Verify that release was not called because obj was None
            mock_release.assert_not_called()

        pool.shutdown()

    def test_pool_context_complete_workflow_with_mock(self):
        """Test complete PoolContext workflow with mocked successful acquisition."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        mock_obj = Mock()

        with (
            patch.object(pool, "acquire") as mock_acquire,
            patch.object(pool, "release") as mock_release,
        ):
            # Mock successful acquisition
            mock_acquire.return_value = (42, "success_key", mock_obj)

            context = PoolContext(pool, "test_arg", test_kwarg="value")

            # Test successful enter
            result = context.__enter__()  # pylint: disable=C2801
            assert result is mock_obj
            assert context.obj_id == 42
            assert context.key == "success_key"
            assert context.obj is mock_obj

            # Verify acquire was called with correct arguments
            mock_acquire.assert_called_once_with("test_arg", test_kwarg="value")

            # Test exit calls release
            context.__exit__(None, None, None)
            mock_release.assert_called_once_with(42, "success_key", mock_obj)

        pool.shutdown()

    def test_pool_context_with_exception_during_acquire(self):
        """Test PoolContext when acquire itself raises an exception."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with patch.object(pool, "acquire") as mock_acquire:
            # Mock acquire to raise an exception
            mock_acquire.side_effect = RuntimeError("Pool exhausted")

            context = PoolContext(pool)

            # Enter should propagate the exception from acquire
            with pytest.raises(RuntimeError, match="Pool exhausted"):
                context.__enter__()  # pylint: disable=C2801

            # Verify that obj_id, key, obj remain None after failed acquire
            assert context.obj_id is None
            assert context.key is None
            assert context.obj is None

        pool.shutdown()

    def test_context_manager_enter_exit(self):
        """Test SmartObjectManager as context manager."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        # Test __enter__
        context_pool = pool.__enter__()  # pylint: disable=C2801
        assert context_pool is pool

        # Test __exit__
        with patch.object(pool, "shutdown") as mock_shutdown:
            pool.__exit__(None, None, None)
            mock_shutdown.assert_called_once()

    def test_context_manager_with_statement(self):
        """Test SmartObjectManager used with 'with' statement."""
        with patch.object(SmartObjectManager, "shutdown") as mock_shutdown:
            with SmartObjectManager(
                factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
            ) as pool:
                assert isinstance(pool, SmartObjectManager)
            mock_shutdown.assert_called_once()


class TestSmartObjectManagerAcquireRelease:
    """Tests for SmartObjectManager acquire and release operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = MockFactory()

    def test_handle_pool_miss_with_logging_enabled(self):
        """Test _handle_pool_miss with logging enabled to cover DEBUG log statement."""
        config = MemoryConfig()
        config.enable_logging = True

        pool = SmartObjectManager(
            factory=self.factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        with patch("smartpool.core.smartpool_manager.safe_log") as mock_log:
            # Call _handle_pool_miss directly to test the logging
            key = "test_key"
            pooled_obj = pool._handle_pool_miss(key, config)

            # Verify the DEBUG log was called with the expected message
            mock_log.assert_called_with(
                pool.logger, logging.DEBUG, f"Pool miss for key {key}, created new object"
            )
            assert isinstance(pooled_obj, PooledObject)
            assert pooled_obj.obj is not None

        pool.shutdown()

    def test_acquire_with_logging_enabled(self):
        """Test acquire process with logging enabled."""
        config = MemoryConfig()
        config.enable_logging = True

        with patch("smartpool.core.smartpool_manager.logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            pool = SmartObjectManager(
                factory=self.factory,
                default_config=config,
                pool_config=PoolConfiguration(register_atexit=False),
            )

            # Mock a pool hit scenario
            with patch.object(pool.operations_manager, "find_valid_object_with_retry") as mock_find:
                mock_result = Mock()
                mock_result.success = True
                mock_result.object_found = PooledObject(
                    obj=Mock(),
                    created_at=time.time(),
                    last_accessed=time.time(),
                    access_count=0,
                    state=ObjectState.VALID,
                    estimated_size=100,
                )
                mock_find.return_value = mock_result

                _, _, obj = pool.acquire()
                assert obj is not None

            pool.shutdown()

    def test_acquire_with_exception(self):
        """Test acquire process with logging enabled."""
        config = MemoryConfig()
        config.enable_logging = True

        pool = SmartObjectManager(
            factory=self.factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        # Mock a pool hit scenario
        with patch.object(pool.operations_manager, "find_valid_object_with_retry") as mock_find:
            mock_result = Mock()
            mock_result.success = True
            mock_result.object_found = None
            mock_find.return_value = mock_result

            with pytest.raises(ObjectStateCorruptedError):
                _, _, _ = pool.acquire()

            pool.shutdown()

    def test_handle_pool_miss_with_factory_exception(self):
        """Test _handle_pool_miss when factory.create raises an exception."""
        config = MemoryConfig()
        config.enable_logging = True

        # Create a factory that raises an exception
        failing_factory = Mock(spec=ObjectFactory)
        failing_factory.get_key.return_value = "test_key"
        failing_factory.create.side_effect = RuntimeError("Factory failed")

        with patch("smartpool.core.smartpool_manager.logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            pool = SmartObjectManager(
                factory=failing_factory,
                default_config=config,
                pool_config=PoolConfiguration(register_atexit=False),
            )

            with pytest.raises(ObjectCreationFailedError):
                pool.acquire()

            pool.shutdown()

    def test_release_validation_failure(self):
        """Test release when validation fails."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        # Mock validation failure
        with patch.object(pool.operations_manager, "validate_and_reset_object", return_value=False):
            mock_obj = Mock()
            pool.release(1, "test_key", mock_obj)
            # Should return early without adding to pool

        pool.shutdown()

    def test_release_pool_full(self):
        """Test release when pool is full."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        # Mock that pool is full
        with (
            patch.object(pool.operations_manager, "validate_and_reset_object", return_value=True),
            patch.object(pool.operations_manager, "should_add_to_pool", return_value=False),
            patch("smartpool.core.smartpool_manager.safe_log") as mock_log,
        ):
            mock_obj = Mock()
            pool.release(1, "test_key", mock_obj)
            mock_log.assert_called()

        pool.shutdown()

    def test_release_destroy_exception(self):
        """Test release when factory.destroy raises an exception."""
        # Create a factory that raises exception on destroy
        failing_factory = Mock(spec=ObjectFactory)
        failing_factory.get_key.return_value = "test_key"
        failing_factory.create.return_value = Mock()
        failing_factory.reset.return_value = True
        failing_factory.validate.return_value = True
        failing_factory.estimate_size.return_value = 100
        failing_factory.destroy.side_effect = AttributeError("Destroy failed")

        pool = SmartObjectManager(
            factory=failing_factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with (
            patch.object(pool.operations_manager, "validate_and_reset_object", return_value=True),
            patch.object(pool.operations_manager, "should_add_to_pool", return_value=False),
            patch("smartpool.core.smartpool_manager.safe_log") as mock_log,
        ):
            mock_obj = Mock()
            pool.release(1, "test_key", mock_obj)
            mock_log.assert_called()

        pool.shutdown()

    def test_release_destroy_exception_connection_error(self):
        """Test release when factory.destroy raises an exception connection error."""
        # Create a factory that raises exception on destroy
        failing_factory = Mock(spec=ObjectFactory)
        failing_factory.get_key.return_value = "test_key"
        failing_factory.create.return_value = Mock()
        failing_factory.reset.return_value = True
        failing_factory.validate.return_value = True
        failing_factory.estimate_size.return_value = 100
        failing_factory.destroy.side_effect = ConnectionError("Destroy failed")

        pool = SmartObjectManager(
            factory=failing_factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with (
            patch.object(pool.operations_manager, "validate_and_reset_object", return_value=True),
            patch.object(pool.operations_manager, "should_add_to_pool", return_value=False),
            patch("smartpool.core.smartpool_manager.safe_log") as mock_log,
        ):
            mock_obj = Mock()
            pool.release(1, "test_key", mock_obj)
            mock_log.assert_called()

        pool.shutdown()

    def test_release_destroy_exception_memory_error(self):
        """Test release when factory.destroy raises an exception memory error."""
        # Create a factory that raises exception on destroy
        failing_factory = Mock(spec=ObjectFactory)
        failing_factory.get_key.return_value = "test_key"
        failing_factory.create.return_value = Mock()
        failing_factory.reset.return_value = True
        failing_factory.validate.return_value = True
        failing_factory.estimate_size.return_value = 100
        failing_factory.destroy.side_effect = MemoryError("Destroy failed")

        pool = SmartObjectManager(
            factory=failing_factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with (
            patch.object(pool.operations_manager, "validate_and_reset_object", return_value=True),
            patch.object(pool.operations_manager, "should_add_to_pool", return_value=False),
            patch("smartpool.core.smartpool_manager.safe_log") as mock_log,
        ):
            mock_obj = Mock()
            pool.release(1, "test_key", mock_obj)
            mock_log.assert_called()

        pool.shutdown()

    def test_release_destroy_exception_io_error(self):
        """Test release when factory.destroy raises an exception ioerror."""
        # Create a factory that raises exception on destroy
        failing_factory = Mock(spec=ObjectFactory)
        failing_factory.get_key.return_value = "test_key"
        failing_factory.create.return_value = Mock()
        failing_factory.reset.return_value = True
        failing_factory.validate.return_value = True
        failing_factory.estimate_size.return_value = 100
        failing_factory.destroy.side_effect = IOError("Destroy failed")

        pool = SmartObjectManager(
            factory=failing_factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with (
            patch.object(pool.operations_manager, "validate_and_reset_object", return_value=True),
            patch.object(pool.operations_manager, "should_add_to_pool", return_value=False),
            patch("smartpool.core.smartpool_manager.safe_log") as mock_log,
        ):
            mock_obj = Mock()
            pool.release(1, "test_key", mock_obj)
            mock_log.assert_called()

        pool.shutdown()


class TestSmartObjectManagerFeatureToggles:
    """Tests for SmartObjectManager feature toggles and monitoring."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = MockFactory()

    def test_performance_metrics_disabled(self):
        """Test acquire when performance metrics are disabled."""
        config = MemoryConfig()
        config.enable_performance_metrics = False

        pool = SmartObjectManager(
            factory=self.factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        assert pool.performance_metrics is None

        obj_id, key, obj = pool.acquire()
        pool.release(obj_id, key, obj)

        pool.shutdown()

    def test_monitoring_disabled(self):
        """Test acquire when monitoring is disabled."""
        pool = SmartObjectManager(
            factory=self.factory,
            pool_config=PoolConfiguration(enable_monitoring=False, register_atexit=False),
        )

        assert pool.optimizer is None

        obj_id, key, obj = pool.acquire()
        pool.release(obj_id, key, obj)

        pool.shutdown()

    def test_async_metrics_mode_initializes_dispatcher(self):
        """Test that async mode initializes dispatcher and emits health gauges."""
        config = MemoryConfig(metrics_mode=MetricsMode.ASYNC)
        pool = SmartObjectManager(
            factory=self.factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        assert pool.metrics_dispatcher is not None

        obj_id, key, obj = pool.acquire()
        pool.release(obj_id, key, obj)
        assert pool.metrics_dispatcher is not None
        assert pool.metrics_dispatcher.flush(1.0)

        metrics = pool.stats.get_all_metrics()
        assert "metrics_queue_depth" in metrics["gauges"]
        assert "metrics_worker_alive" in metrics["gauges"]

        pool.shutdown()
        assert pool.metrics_dispatcher is None

    def test_async_metrics_drop_counter_is_recorded(self):
        """Test dropped metrics events are counted in stats counters."""
        config = MemoryConfig(
            metrics_mode=MetricsMode.ASYNC,
            metrics_queue_maxsize=1,
            metrics_overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
        )
        pool = SmartObjectManager(
            factory=self.factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        with patch.object(pool, "_process_record_acquisition_event") as mock_handler:
            mock_handler.side_effect = lambda payload: time.sleep(0.05)
            # Reinitialize dispatcher so it binds the patched handler.
            pool._shutdown_metrics_dispatcher(1.0)
            pool._initialize_metrics_dispatcher()

            for _ in range(100):
                pool._publish_metrics_event(
                    pool._EVENT_RECORD_ACQUISITION,  # pylint: disable=protected-access
                    {
                        "key": "test_key",
                        "acquisition_time_ms": 1.0,
                        "hit": True,
                        "lock_wait_time_ms": 0.0,
                    },
                )

            assert pool.metrics_dispatcher is not None
            pool.metrics_dispatcher.flush(1.0)
            assert pool.stats.get("metrics_events_dropped") > 0

        pool.shutdown()

    def test_async_metrics_worker_error_is_non_fatal(self):
        """Test worker exceptions are absorbed and counted."""
        config = MemoryConfig(metrics_mode=MetricsMode.ASYNC)
        pool = SmartObjectManager(
            factory=self.factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        with patch.object(pool, "_process_record_acquisition_event") as mock_handler:
            mock_handler.side_effect = RuntimeError("handler failed")
            pool._shutdown_metrics_dispatcher(1.0)
            pool._initialize_metrics_dispatcher()
            pool._publish_metrics_event(
                pool._EVENT_RECORD_ACQUISITION,  # pylint: disable=protected-access
                {
                    "key": "test_key",
                    "acquisition_time_ms": 1.0,
                    "hit": True,
                    "lock_wait_time_ms": 0.0,
                },
            )

            assert pool.metrics_dispatcher is not None
            assert pool.metrics_dispatcher.flush(1.0)
            assert pool.stats.get("metrics_worker_errors") >= 1

        # Pool must still be usable after worker handler error.
        obj_id, key, obj = pool.acquire()
        pool.release(obj_id, key, obj)
        pool.shutdown()

    def test_async_adaptive_sampling_is_disabled_when_auto_tuning_enabled(self):
        """Auto-tuning must keep full acquisition signal quality."""
        config = MemoryConfig(
            metrics_mode=MetricsMode.ASYNC,
            metrics_queue_maxsize=8,
            metrics_overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
        )
        pool = SmartObjectManager(
            factory=self.factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        # Enable optimizer loop: adaptive async sampling should be bypassed.
        pool.enable_auto_tuning(interval_seconds=9999.0)
        assert pool.metrics_dispatcher is not None
        with patch.object(pool.metrics_dispatcher, "get_queue_depth_ratio", return_value=1.0):
            # Even under max queue pressure, events must be retained for optimizer quality.
            assert all(pool._should_keep_async_record_event() for _ in range(64))

        pool.shutdown()

    def test_auto_tuning_with_optimizer_disabled(self):
        """Test auto-tuning methods when optimizer is disabled."""
        pool = SmartObjectManager(
            factory=self.factory,
            pool_config=PoolConfiguration(enable_monitoring=False, register_atexit=False),
        )

        with patch("smartpool.core.smartpool_manager.safe_log") as mock_log:
            pool.enable_auto_tuning()
            mock_log.assert_called_with(
                pool.logger,
                logging.WARNING,
                "Auto-tuning cannot be enabled:"
                " optimizer not initialized. Ensure enable_monitoring is True.",
            )

            pool.disable_auto_tuning()
            mock_log.assert_called_with(
                pool.logger,
                logging.WARNING,
                "Auto-tuning cannot be disabled: optimizer not initialized.",
            )

        pool.shutdown()

    def test_auto_tuning_with_optimizer_enabled(self):
        """Test auto-tuning methods when optimizer is enabled."""
        pool = SmartObjectManager(
            factory=self.factory,
            pool_config=PoolConfiguration(enable_monitoring=True, register_atexit=False),
        )

        # pylint: disable=no-member
        with (
            patch.object(pool.optimizer, "enable_auto_tuning") as mock_enable,
            patch.object(pool.optimizer, "disable_auto_tuning") as mock_disable,
        ):
            pool.enable_auto_tuning(600.0)
            mock_enable.assert_called_once_with(600.0)

            pool.disable_auto_tuning()
            mock_disable.assert_called_once()
        # pylint: enable=no-member

        pool.shutdown()


class TestSmartObjectManagerCleanupAndStats:
    """Tests for SmartObjectManager cleanup operations and statistics."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = MockFactory()

    def test_force_cleanup_success(self):
        """Test force_cleanup when it succeeds."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with patch.object(pool.background_manager, "force_cleanup_now") as mock_cleanup:
            mock_cleanup.return_value = {"success": True, "objects_cleaned": 5}

            result = pool.force_cleanup()
            assert result == 5

        pool.shutdown()

    def test_force_cleanup_failure(self):
        """Test force_cleanup when it fails."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with patch.object(pool.background_manager, "force_cleanup_now") as mock_cleanup:
            mock_cleanup.return_value = {"success": False}

            result = pool.force_cleanup()
            assert result == 0

        pool.shutdown()

    def test_get_basic_stats_comprehensive(self):
        """Test get_basic_stats with various pool states."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        # Add some objects to pool
        pool.pool["key1"] = deque(
            [
                PooledObject(
                    Mock(), time.time(), time.time(), state=ObjectState.VALID, estimated_size=100
                ),
                PooledObject(
                    Mock(), time.time(), time.time(), state=ObjectState.VALID, estimated_size=100
                ),
            ]
        )
        pool.pool["key2"] = deque(
            [
                PooledObject(
                    Mock(), time.time(), time.time(), state=ObjectState.VALID, estimated_size=100
                )
            ]
        )

        # Mock some corruption stats
        with patch.object(
            pool.operations_manager, "get_corruption_stats", return_value={"key1": 2}
        ):
            stats = pool.get_basic_stats()

            assert stats["total_pooled_objects"] == 3
            assert stats["corrupted_keys_count"] == 1
            assert stats["pool_keys_count"] == 2

        pool.shutdown()


class TestSmartObjectManagerErrorHandling:
    """Tests for SmartObjectManager error handling and logging."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = MockFactory()

    def test_safe_shutdown_with_runtime_exception(self):
        """Test _safe_shutdown when shutdown raises a runtime exception."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with (
            patch.object(pool, "shutdown", side_effect=RuntimeError("Shutdown failed")),
            patch("smartpool.core.smartpool_manager.safe_log") as mock_log,
        ):
            pool._safe_shutdown()
            mock_log.assert_called_with(
                pool.logger,
                logging.ERROR,
                "Threading error during atexit shutdown: Shutdown failed",
            )

    def test_safe_shutdown_with_timeout_exception(self):
        """Test _safe_shutdown when shutdown raise an timeout exception."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with (
            patch.object(pool, "shutdown", side_effect=TimeoutError("Shutdown failed")),
            patch("smartpool.core.smartpool_manager.safe_log") as mock_log,
        ):
            pool._safe_shutdown()
            mock_log.assert_called_with(
                pool.logger,
                logging.ERROR,
                "Timeout error during atexit shutdown: Shutdown failed",
            )

    def test_safe_shutdown_with_attribute_exception(self):
        """Test _safe_shutdown when shutdown raise an attribute exception."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with (
            patch.object(pool, "shutdown", side_effect=AttributeError("Shutdown failed")),
            patch("smartpool.core.smartpool_manager.safe_log") as mock_log,
        ):
            pool._safe_shutdown()
            mock_log.assert_called_with(
                pool.logger,
                logging.ERROR,
                "Object state error during atexit shutdown: Shutdown failed",
            )

    def test_safe_shutdown_with_os_error(self):
        """Test _safe_shutdown when shutdown raise an os error."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with (
            patch.object(pool, "shutdown", side_effect=OSError("Shutdown failed")),
            patch("smartpool.core.smartpool_manager.safe_log") as mock_log,
        ):
            pool._safe_shutdown()
            mock_log.assert_called_with(
                pool.logger,
                logging.ERROR,
                "System resource error during atexit shutdown: Shutdown failed",
            )

    def test_safe_shutdown_with_memory_error(self):
        """Test _safe_shutdown when shutdown raise a memory error."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with (
            patch.object(pool, "shutdown", side_effect=MemoryError("Shutdown failed")),
            patch("smartpool.core.smartpool_manager.safe_log") as mock_log,
        ):
            pool._safe_shutdown()
            mock_log.assert_called_with(
                pool.logger,
                logging.CRITICAL,
                "Memory error during atexit shutdown: Shutdown failed",
            )

    def test_safe_log_with_disabled_logger(self):
        """Test _safe_log when logger is disabled for the level."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with patch.object(pool.logger, "isEnabledFor", return_value=False):
            # Should not raise exception
            safe_log(pool.logger, logging.DEBUG, "Test message")

        pool.shutdown()

    def test_safe_log_with_value_error(self):
        """Test _safe_log when logger raises ValueError."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with patch.object(pool.logger, "log", side_effect=ValueError("Logger error")):
            # Should not raise exception
            safe_log(pool.logger, logging.INFO, "Test message")

        pool.shutdown()

    def test_safe_log_with_os_error(self):
        """Test _safe_log when logger raises OSError."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with patch.object(pool.logger, "log", side_effect=OSError("Stream error")):
            # Should not raise exception
            safe_log(pool.logger, logging.INFO, "Test message")

        pool.shutdown()

    def test_safe_log_with_unexpected_exception(self):
        """Test _safe_log when logger raises unexpected exception."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

        with patch.object(pool.logger, "log", side_effect=RuntimeError("Unexpected error")):
            # Should not raise exception
            safe_log(pool.logger, logging.INFO, "Test message")

        pool.shutdown()

    def test_safe_log_with_none_logger(self):
        """Test _safe_log when logger is None."""
        pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )
        pool.logger = None

        # Should not raise exception
        safe_log(pool.logger, logging.INFO, "Test message")

        pool.shutdown()


class TestSmartObjectManagerHandleException:
    """Tests for SmartObjectManager _handle_exception method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = MockFactory()
        self.pool = SmartObjectManager(
            factory=self.factory, pool_config=PoolConfiguration(register_atexit=False)
        )

    def test_handle_exception_no_raise(self):
        """Test that _handle_exception records the exception but does not re-raise."""
        exc = ObjectStateCorruptedError("test error")
        with (
            patch.object(self.pool.exception_metrics, "record_exception") as mock_record,
            patch.object(self.pool.exception_policy, "should_raise", return_value=False),
        ):
            self.pool._handle_exception(exc)
            mock_record.assert_called_once_with(exc)

    def test_handle_exception_with_raise(self):
        """Test that _handle_exception records the exception and re-raises."""
        exc = ObjectStateCorruptedError("test error")
        with (
            patch.object(self.pool.exception_metrics, "record_exception") as mock_record,
            patch.object(self.pool.exception_policy, "should_raise", return_value=True),
        ):
            with pytest.raises(ObjectStateCorruptedError):
                self.pool._handle_exception(exc)
            mock_record.assert_called_once_with(exc)

    def teardown_method(self):
        """Tear down test fixtures."""
        self.pool.shutdown()
