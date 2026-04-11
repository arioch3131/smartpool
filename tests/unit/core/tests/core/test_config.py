"""Tests for the MemoryConfig and MemoryConfigFactory classes."""

import pytest

from smartpool.config import (
    MemoryConfig,
    MemoryConfigFactory,
    MemoryPreset,
    MetricsMode,
    MetricsOverloadPolicy,
)
from smartpool.core.exceptions.configuration_error import (
    InvalidPoolSizeError,
    InvalidTTLError,
    PoolConfigurationError,
)


class TestMemoryConfig:
    """Test suite for the MemoryConfig class."""

    def test_default_values(self):
        """Test that MemoryConfig has sane default values."""
        config = MemoryConfig()
        assert config.max_objects_per_key > 0
        assert config.ttl_seconds > 0
        assert config.cleanup_interval_seconds > 0
        assert config.enable_performance_metrics
        assert config.metrics_mode == MetricsMode.SYNC
        assert config.metrics_queue_maxsize > 0
        assert config.metrics_sample_rate == 1
        assert config.metrics_flush_timeout_seconds > 0
        assert config.metrics_overload_policy == MetricsOverloadPolicy.DROP_NEWEST

    def test_parameter_validation(self):
        """Test that invalid parameters raise a ValueError."""
        with pytest.raises(InvalidPoolSizeError):
            MemoryConfig(max_objects_per_key=0)
        with pytest.raises(InvalidTTLError):
            MemoryConfig(ttl_seconds=-10)
        with pytest.raises(PoolConfigurationError):
            MemoryConfig(cleanup_interval_seconds=0)
        with pytest.raises(PoolConfigurationError):
            MemoryConfig(max_expected_concurrency=0)
        with pytest.raises(PoolConfigurationError):
            MemoryConfig(object_creation_cost="invalid_cost")
        with pytest.raises(PoolConfigurationError):
            MemoryConfig(memory_pressure="invalid_pressure")
        with pytest.raises(PoolConfigurationError):
            MemoryConfig(metrics_mode="invalid_mode")
        with pytest.raises(PoolConfigurationError):
            MemoryConfig(metrics_queue_maxsize=0)
        with pytest.raises(PoolConfigurationError):
            MemoryConfig(metrics_sample_rate=0)
        with pytest.raises(PoolConfigurationError):
            MemoryConfig(metrics_flush_timeout_seconds=0)
        with pytest.raises(PoolConfigurationError):
            MemoryConfig(metrics_overload_policy="invalid_policy")


class TestMemoryConfigFactory:
    """Test suite for the MemoryConfigFactory class."""

    def test_create_all_presets(self):
        """Test that the factory can create a config for every defined preset."""
        default_config = MemoryConfig()  # Get default config once
        for preset in MemoryPreset:
            config = MemoryConfigFactory.create_preset(preset)
            assert isinstance(config, MemoryConfig)
            assert config.metrics_mode == MetricsMode.SYNC
            assert config.metrics_queue_maxsize > 0
            assert config.metrics_sample_rate > 0
            assert config.metrics_flush_timeout_seconds > 0
            assert isinstance(config.metrics_overload_policy, MetricsOverloadPolicy)

            if preset == MemoryPreset.CUSTOM:
                assert config.max_objects_per_key == default_config.max_objects_per_key
                assert config.ttl_seconds == default_config.ttl_seconds
                # Add more assertions for other default values if necessary
            elif preset == MemoryPreset.DATABASE_CONNECTIONS:
                # DATABASE_CONNECTIONS specifically has max_objects_per_key=20, which is the default
                assert config.max_objects_per_key == 20
                # Add other specific assertions for DATABASE_CONNECTIONS if needed
            else:
                # For other presets, ensure they are not the default config
                assert config.max_objects_per_key != default_config.max_objects_per_key

    def test_high_throughput_preset_values(self):
        """Test the specific values of the HIGH_THROUGHPUT preset."""
        config = MemoryConfigFactory.create_preset(MemoryPreset.HIGH_THROUGHPUT)
        assert config.max_objects_per_key >= 50
        assert config.ttl_seconds >= 1000
        assert not config.enable_logging

    def test_low_memory_preset_values(self):
        """Test the specific values of the LOW_MEMORY preset."""
        config = MemoryConfigFactory.create_preset(MemoryPreset.LOW_MEMORY)
        assert config.max_objects_per_key <= 10
        assert config.ttl_seconds <= 120
        assert not config.enable_performance_metrics

    def test_development_preset_values(self):
        """Test the specific values of the DEVELOPMENT preset."""
        config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        assert config.enable_logging
        assert config.ttl_seconds <= 60
        assert config.max_corrupted_objects == 1

    def test_get_preset_recommendations(self):
        """Test that recommendations are available for all presets."""
        recommendations = MemoryConfigFactory.get_preset_recommendations()
        for preset in MemoryPreset:
            assert preset in recommendations
            assert isinstance(recommendations[preset], str)

    def test_auto_tune_config_logic(self):
        """Test the auto-tuning logic for adjusting configuration."""
        base_config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        original_max_objects_per_key = base_config.max_objects_per_key

        # Scenario 1: Low hit rate -> should increase pool size
        low_hit_rate_metrics = {
            "hit_rate": 0.2,
            "avg_acquisition_time_ms": 5.0,
            "lock_contention_rate": 0.1,
        }
        tuned_config_1 = MemoryConfigFactory.auto_tune_config(base_config, low_hit_rate_metrics)
        assert tuned_config_1.max_objects_per_key > original_max_objects_per_key

        # Scenario 2: High acquisition time -> should decrease validation attempts
        high_latency_metrics = {
            "hit_rate": 0.8,
            "avg_acquisition_time_ms": 20.0,
            "lock_contention_rate": 0.1,
        }
        tuned_config_2 = MemoryConfigFactory.auto_tune_config(base_config, high_latency_metrics)
        assert tuned_config_2.max_validation_attempts < base_config.max_validation_attempts

        # Scenario 3: High lock contention -> should increase cleanup interval
        high_contention_metrics = {
            "hit_rate": 0.8,
            "avg_acquisition_time_ms": 5.0,
            "lock_contention_rate": 0.4,
        }
        tuned_config_3 = MemoryConfigFactory.auto_tune_config(base_config, high_contention_metrics)
        assert tuned_config_3.cleanup_interval_seconds > base_config.cleanup_interval_seconds
