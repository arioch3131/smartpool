"""Tests for the MemoryManager class."""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from smartpool.config import MemoryConfig, MemoryConfigFactory, MemoryPreset
from smartpool.core.managers import MemoryManager


class TestMemoryManagerBase:  # pylint: disable=R0903,W0201
    """Base class for MemoryManager tests, providing common setup."""

    def setup_method(self):
        """Set up mock objects and MemoryManager instance for each test."""
        # Mock the main pool and its components
        self.mock_pool = Mock()
        self.mock_pool.current_preset = MemoryPreset.DEVELOPMENT
        self.mock_pool.default_config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        self.mock_pool.get_basic_stats.return_value = {"hits": 10, "misses": 5}
        self.mock_pool.lock = MagicMock()  # Use MagicMock for context manager support

        self.mock_pool.performance_metrics = Mock()
        self.mock_pool.performance_metrics.get_performance_report.return_value = {
            "current_metrics": {"hit_rate": 0.66}
        }

        self.mock_pool.optimizer = Mock()
        self.mock_pool.optimizer.get_tuning_info.return_value = {"enabled": False}

        self.manager = MemoryManager(self.mock_pool)


class TestMemoryManagerPerformanceReports(TestMemoryManagerBase):
    """Tests for performance report generation in MemoryManager."""

    def test_get_performance_report(self):
        """Test that performance reports are correctly assembled."""
        report = self.manager.get_performance_report(detailed=True)

        assert "basic_stats" in report
        assert "preset" in report
        assert "performance" in report
        assert "auto_tuning" in report
        assert report["preset"] == MemoryPreset.DEVELOPMENT.value
        self.mock_pool.get_basic_stats.assert_called_once()
        self.mock_pool.performance_metrics.get_performance_report.assert_called_once()

    def test_get_performance_report_no_optimizer(self):
        """Test that auto_tuning is correctly reported when no optimizer is available."""
        self.mock_pool.optimizer = None  # Simulate no optimizer
        report = self.manager.get_performance_report(detailed=True)

        assert "auto_tuning" in report
        assert report["auto_tuning"] == {
            "enabled": False,
            "interval": 0,
            "last_run": 0,
            "adjustments_count": 0,
        }
        self.mock_pool.get_basic_stats.assert_called_once()
        self.mock_pool.performance_metrics.get_performance_report.assert_called_once()

    def test_get_performance_report_no_performance_metrics(self):
        """Test get_performance_report when performance_metrics are not available."""
        self.mock_pool.performance_metrics = None
        report = self.manager.get_performance_report(detailed=True)
        assert "performance" not in report
        assert "key_statistics" not in report


# pylint: disable=protected-access
class TestMemoryManagerPresetManagement(TestMemoryManagerBase):
    """Tests for preset management functionalities in MemoryManager."""

    def test_get_preset_info(self):
        """Test the structure and content of preset information."""
        with patch.object(self.manager, "_compare_with_presets") as mock_compare:
            mock_compare.return_value = {"high_throughput": {"max_objects_per_key_diff": 90}}
            preset_info = self.manager.get_preset_info()

            assert preset_info["current_preset"] == MemoryPreset.DEVELOPMENT.value
            assert "available_presets" in preset_info
            assert MemoryPreset.HIGH_THROUGHPUT.value in preset_info["preset_comparison"]
            mock_compare.assert_called_once()

    def test_compare_with_presets_no_performance_metrics(self):
        """Test _compare_with_presets when no performance metrics are available."""
        self.mock_pool.performance_metrics = None
        comparisons = self.manager._compare_with_presets()
        assert MemoryPreset.HIGH_THROUGHPUT.value in comparisons
        assert (
            "Unknown impact" in comparisons[MemoryPreset.HIGH_THROUGHPUT.value]["expected_impact"]
        )

    def test_compare_with_presets_with_performance_metrics(self):
        """Test _compare_with_presets when performance metrics are available."""
        mock_snapshot = Mock()
        mock_snapshot.hit_rate = 0.5
        self.mock_pool.performance_metrics.create_snapshot.return_value = mock_snapshot
        comparisons = self.manager._compare_with_presets()
        assert MemoryPreset.HIGH_THROUGHPUT.value in comparisons
        assert (
            "Probable improvement"
            in comparisons[MemoryPreset.HIGH_THROUGHPUT.value]["expected_impact"]
        )

    def test_estimate_preset_impact(self):
        """Test _estimate_preset_impact logic."""
        mock_snapshot = Mock()
        mock_snapshot.hit_rate = 0.5

        # Case 1: Increase max_objects_per_key, low hit rate
        preset_config = MemoryConfigFactory.create_preset(MemoryPreset.HIGH_THROUGHPUT)
        impact = self.manager._estimate_preset_impact(preset_config, mock_snapshot)
        assert "Probable improvement in hit rate and performance" in impact

        # Case 2: Increase max_objects_per_key, high hit rate
        mock_snapshot.hit_rate = 0.7
        impact = self.manager._estimate_preset_impact(preset_config, mock_snapshot)
        assert "Increased memory consumption" in impact

        # Case 3: Decrease max_objects_per_key
        preset_config = MemoryConfigFactory.create_preset(MemoryPreset.LOW_MEMORY)
        impact = self.manager._estimate_preset_impact(preset_config, mock_snapshot)
        assert "Memory reduction" in impact

        # Case 4: Same max_objects_per_key
        preset_config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        impact = self.manager._estimate_preset_impact(preset_config, mock_snapshot)
        assert "Limited impact" in impact

        # Case 5: No snapshot - Corriger le texte attendu
        impact = self.manager._estimate_preset_impact(preset_config, None)
        assert "Unknown impact" in impact

    def test_estimate_memory_impact(self):
        """Test _estimate_memory_impact logic."""
        # Case 1: High memory impact
        preset_config = MemoryConfig()
        preset_config.max_objects_per_key = self.mock_pool.default_config.max_objects_per_key + 25
        impact = self.manager._estimate_memory_impact(preset_config)
        assert "high memory impact" in impact

        # Case 2: Moderate memory impact
        preset_config.max_objects_per_key = self.mock_pool.default_config.max_objects_per_key + 10
        impact = self.manager._estimate_memory_impact(preset_config)
        assert "moderate memory impact" in impact

        # Case 3: Memory reduction
        preset_config.max_objects_per_key = self.mock_pool.default_config.max_objects_per_key - 10
        impact = self.manager._estimate_memory_impact(preset_config)
        assert "memory reduction" in impact

        # Case 4: Negligible memory impact
        preset_config.max_objects_per_key = self.mock_pool.default_config.max_objects_per_key + 2
        impact = self.manager._estimate_memory_impact(preset_config)
        assert "Negligible memory impact" in impact

    def test_estimate_performance_impact(self):
        """Test _estimate_performance_impact logic."""
        # Case 1: Increase max_objects_per_key, low hit rate
        preset_config = MemoryConfig()
        preset_config.max_objects_per_key = self.mock_pool.default_config.max_objects_per_key + 10
        self.mock_pool.get_basic_stats.return_value = {"reuses": 10, "creates": 20}
        impact = self.manager._estimate_performance_impact(preset_config)
        assert "Expected improvement" in impact

        # Case 2: Increase ttl_seconds
        preset_config = MemoryConfig()
        preset_config.max_objects_per_key = self.mock_pool.default_config.max_objects_per_key
        preset_config.ttl_seconds = self.mock_pool.default_config.ttl_seconds + 100
        impact = self.manager._estimate_performance_impact(preset_config)
        assert "Increased reuse" in impact

        # Case 3: Decrease max_validation_attempts
        preset_config = MemoryConfig()
        preset_config.max_objects_per_key = self.mock_pool.default_config.max_objects_per_key
        preset_config.ttl_seconds = self.mock_pool.default_config.ttl_seconds
        preset_config.max_validation_attempts = (
            self.mock_pool.default_config.max_validation_attempts - 1
        )
        impact = self.manager._estimate_performance_impact(preset_config)
        assert "Reduced acquisition time" in impact

        # Case 4: Neutral impact
        preset_config = MemoryConfig()
        preset_config.max_objects_per_key = self.mock_pool.default_config.max_objects_per_key
        preset_config.ttl_seconds = self.mock_pool.default_config.ttl_seconds
        preset_config.max_validation_attempts = (
            self.mock_pool.default_config.max_validation_attempts
        )
        impact = self.manager._estimate_performance_impact(preset_config)
        assert "Neutral performance impact" in impact

    def test_switch_preset(self):
        """Test the logic for switching the pool's preset configuration."""
        result = self.manager.switch_preset(MemoryPreset.HIGH_THROUGHPUT)

        assert result["success"]
        assert result["new_preset"] == MemoryPreset.HIGH_THROUGHPUT.value
        # Check that the pool's config and preset were updated
        assert self.mock_pool.current_preset == MemoryPreset.HIGH_THROUGHPUT
        assert isinstance(self.mock_pool.default_config, object)

    @patch("smartpool.core.managers.memory_manager.PerformanceMetrics")
    def test_switch_preset_performance_metrics_handling(self, mock_performance_metrics):
        """Test that performance metrics are correctly enabled/disabled during preset switch."""
        # Case 1: Performance metrics are currently enabled, new preset disables them
        self.mock_pool.performance_metrics = Mock()
        new_config_disable = MemoryConfigFactory.create_preset(
            MemoryPreset.LOW_MEMORY
        )  # Assuming LOW_MEMORY disables metrics
        new_config_disable.enable_performance_metrics = False
        with patch(
            "smartpool.config.MemoryConfigFactory.create_preset",
            return_value=new_config_disable,
        ):
            self.manager.switch_preset(MemoryPreset.LOW_MEMORY)
            assert self.mock_pool.performance_metrics is None
            self.mock_pool.lock.__enter__.assert_called_once()  # Ensure lock was acquired
            self.mock_pool.lock.__exit__.assert_called_once()  # Ensure lock was released
            self.mock_pool.lock.__enter__.reset_mock()
            self.mock_pool.lock.__exit__.reset_mock()

        # Case 2: Performance metrics are currently disabled, new preset enables them
        self.mock_pool.performance_metrics = None
        new_config_enable = MemoryConfigFactory.create_preset(
            MemoryPreset.HIGH_THROUGHPUT
        )  # Assuming HIGH_THROUGHPUT enables metrics
        new_config_enable.enable_performance_metrics = True
        new_config_enable.max_performance_history_size = 100
        new_config_enable.enable_acquisition_tracking = True
        with patch(
            "smartpool.config.MemoryConfigFactory.create_preset",
            return_value=new_config_enable,
        ):
            self.manager.switch_preset(MemoryPreset.HIGH_THROUGHPUT)
            assert self.mock_pool.performance_metrics is not None
            mock_performance_metrics.assert_called_once_with(
                history_size=new_config_enable.max_performance_history_size,
                enable_detailed_tracking=new_config_enable.enable_acquisition_tracking,
            )
            self.mock_pool.lock.__enter__.assert_called_once()
            self.mock_pool.lock.__exit__.assert_called_once()
            self.mock_pool.lock.__enter__.reset_mock()
            self.mock_pool.lock.__exit__.reset_mock()
            mock_performance_metrics.reset_mock()

        # Case 3: Performance metrics are currently enabled, new preset also enables them
        existing_metrics_mock = Mock()
        self.mock_pool.performance_metrics = existing_metrics_mock
        new_config_no_change_enable = MemoryConfigFactory.create_preset(
            MemoryPreset.HIGH_THROUGHPUT
        )
        new_config_no_change_enable.enable_performance_metrics = True
        with patch(
            "smartpool.config.MemoryConfigFactory.create_preset",
            return_value=new_config_no_change_enable,
        ):
            self.manager.switch_preset(MemoryPreset.HIGH_THROUGHPUT)
            assert self.mock_pool.performance_metrics == existing_metrics_mock
            mock_performance_metrics.assert_not_called()  # Should not be re-instantiated
            self.mock_pool.lock.__enter__.assert_called_once()
            self.mock_pool.lock.__exit__.assert_called_once()
            self.mock_pool.lock.__enter__.reset_mock()
            self.mock_pool.lock.__exit__.reset_mock()

        # Case 4: Performance metrics are currently disabled, new preset also disables them
        self.mock_pool.performance_metrics = None
        new_config_no_change_disable = MemoryConfigFactory.create_preset(MemoryPreset.LOW_MEMORY)
        new_config_no_change_disable.enable_performance_metrics = False
        with patch(
            "smartpool.config.MemoryConfigFactory.create_preset",
            return_value=new_config_no_change_disable,
        ):
            self.manager.switch_preset(MemoryPreset.LOW_MEMORY)
            assert self.mock_pool.performance_metrics is None
            mock_performance_metrics.assert_not_called()
            self.mock_pool.lock.__enter__.assert_called_once()
            self.mock_pool.lock.__exit__.assert_called_once()
            self.mock_pool.lock.__enter__.reset_mock()
            self.mock_pool.lock.__exit__.reset_mock()


class TestMemoryManagerHealthAndStats(TestMemoryManagerBase):
    """Tests for health status and detailed statistics in MemoryManager."""

    def test_get_health_status(self):
        """Test the health status calculation."""
        # Scenario 1: Healthy
        self.mock_pool.get_basic_stats.return_value = {
            "counters": {
                "hits": 10,
                "misses": 10,
                "corrupted": 0,
                "validation_failures": 1,
                "creates": 110,
                "total_requests": 110,
            }
        }
        health = self.manager.get_health_status()
        assert health["status"] == "healthy"
        assert health["hit_rate"] == pytest.approx(10 / 20)
        assert len(health["issues"]) == 0

        # Scenario 2: Warning (low hit rate)
        self.mock_pool.get_basic_stats.return_value = {
            "counters": {
                "hits": 20,
                "misses": 80,
                "corrupted": 0,
                "validation_failures": 1,
                "creates": 100,
                "total_requests": 100,
            }
        }
        health = self.manager.get_health_status()
        assert health["status"] == "warning"

        # Scenario 3: Critical (high corruption AND another issue)
        self.mock_pool.get_basic_stats.return_value = {
            "counters": {
                "hits": 20,
                "misses": 80,
                "corrupted": 20,
                "validation_failures": 1,
                "creates": 30,
                "total_requests": 100,
            }
        }
        health = self.manager.get_health_status()
        assert health["status"] == "critical"
        assert any("High corruption rate" in issue for issue in health["issues"])
        assert any("Very low hit rate" in issue for issue in health["issues"])

    def test_get_detailed_stats(self):
        """Test the aggregation of detailed stats from all components."""
        # Mock the necessary sub-managers and their return values
        pooled_obj_mock = Mock()
        pooled_obj_mock.estimated_size = 100
        pooled_obj_mock.created_at = time.time() - 10
        pooled_obj_mock.last_accessed = time.time() - 5
        pooled_obj_mock.access_count = 2
        pooled_obj_mock.state.value = "valid"

        self.mock_pool.pool = {"key1": [pooled_obj_mock], "key2": []}
        self.mock_pool.active_manager.get_active_objects_count_info.return_value = {
            1: Mock(key="key1", estimated_size=150, created_at=time.time(), access_count=1),
            2: Mock(key="key3", estimated_size=200, created_at=time.time(), access_count=1),
        }
        self.mock_pool.operations_manager.get_lru_stats.return_value = {
            "key1": time.time(),
            "key3": time.time(),
        }
        self.mock_pool.operations_manager.get_corruption_stats.return_value = {"key2": 1}
        self.mock_pool.stats.get_history.return_value = []

        detailed_stats = self.manager.get_detailed_stats()

        assert "general" in detailed_stats
        assert "by_key" in detailed_stats
        assert "key1" in detailed_stats["by_key"]
        assert "key2" in detailed_stats["by_key"]
        assert "key3" in detailed_stats["by_key"]

        key1_stats = detailed_stats["by_key"]["key1"]
        assert key1_stats["pooled_count"] == 1
        assert key1_stats["active_count"] == 1
        assert key1_stats["memory_bytes"] == 250

        key2_stats = detailed_stats["by_key"]["key2"]
        assert key2_stats["corrupted_count"] == 1

        key3_stats = detailed_stats["by_key"]["key3"]
        assert key3_stats["pooled_count"] == 0
        assert key3_stats["active_count"] == 1
        assert key3_stats["memory_bytes"] == 200

    def test_get_health_status_warning_multiple_issues(self):
        """Test get_health_status with exactly one issue leading to warning."""
        self.mock_pool.get_basic_stats.return_value = {
            "counters": {
                "hits": 10,
                "misses": 10,
                "corrupted": 0,
                "validation_failures": 15,
                "creates": 100,
                "total_requests": 100,
            }
        }
        health = self.manager.get_health_status()
        assert health["status"] == "warning"
        assert any("Frequent validation failures" in issue for issue in health["issues"])
        assert len(health["issues"]) == 1

    def test_get_health_status_critical_multiple_issues(self):
        """Test get_health_status with multiple issues leading to critical."""
        self.mock_pool.get_basic_stats.return_value = {
            "counters": {
                "hits": 10,
                "misses": 80,
                "corrupted": 20,
                "validation_failures": 15,
                "creates": 30,
                "total_requests": 100,
            }
        }
        health = self.manager.get_health_status()
        assert health["status"] == "critical"
        assert any("High corruption rate" in issue for issue in health["issues"])
        assert any("Very low hit rate" in issue for issue in health["issues"])
        assert any("Frequent validation failures" in issue for issue in health["issues"])
        assert len(health["issues"]) == 3


class TestMemoryManagerOptimizationRecommendations(TestMemoryManagerBase):
    """Tests for optimization recommendations in MemoryManager."""

    def test_get_optimization_recommendations_no_optimizer(self):
        """Test get_optimization_recommendations when optimizer is not available."""
        self.mock_pool.optimizer = None  # Remove the optimizer
        self.mock_pool.get_basic_stats.return_value = {
            "counters": {
                "hits": 10,
                "misses": 50,
                "creates": 60,
                "corrupted": 0,
            }
        }
        recommendations = self.manager.get_optimization_recommendations()

        assert "current_metrics" in recommendations
        assert "urgency_score" in recommendations
        assert "urgency_level" in recommendations
        assert "recommendations" in recommendations
        assert "note" in recommendations

        # Test low hit rate recommendation
        assert recommendations["urgency_level"] == "info"
        assert len(recommendations["recommendations"]) == 1
        assert recommendations["recommendations"][0]["type"] == "warning"
        assert "HIGH_THROUGHPUT" in recommendations["recommendations"][0]["recommended"]

        # Test high corruption rate recommendation
        self.mock_pool.get_basic_stats.return_value = {
            "counters": {
                "hits": 100,
                "misses": 0,
                "creates": 10,
                "corrupted": 2,
            }
        }
        recommendations = self.manager.get_optimization_recommendations()
        assert recommendations["urgency_level"] == "critical"
        assert len(recommendations["recommendations"]) == 1
        assert recommendations["recommendations"][0]["type"] == "critical"
        assert "DEVELOPMENT" in recommendations["recommendations"][0]["recommended"]

    def test_get_optimization_recommendations_with_optimizer(self):
        """Test get_optimization_recommendations when optimizer is available."""
        self.mock_pool.optimizer = Mock()
        self.mock_pool.optimizer.force_optimization_analysis.return_value = {
            "recommendations": [{"type": "critical"}]
        }

        recommendations = self.manager.get_optimization_recommendations()

        self.mock_pool.optimizer.force_optimization_analysis.assert_called_once()
        assert recommendations["recommendations"][0]["type"] == "critical"


class TestMemoryManagerDashboardSummary(TestMemoryManagerBase):
    """Tests for dashboard summary generation in MemoryManager."""

    def test_get_dashboard_summary_with_optimizer(self):
        """Test get_dashboard_summary when optimizer is available."""
        self.mock_pool.performance_metrics = Mock()
        self.mock_pool.performance_metrics.create_snapshot.return_value = Mock(
            avg_acquisition_time_ms=10.0,
            p95_acquisition_time_ms=20.0,
            acquisitions_per_second=5.0,
            lock_contention_rate=0.1,
        )
        self.mock_pool.optimizer = Mock()
        self.mock_pool.optimizer.force_optimization_analysis.return_value = {
            "recommendations": [{"type": "critical"}, {"type": "warning"}]
        }
        self.mock_pool.get_basic_stats.return_value = {
            "counters": {
                "hits": 10,
                "misses": 5,
                "creates": 10,
                "reuses": 5,
            }
        }
        summary = self.manager.get_dashboard_summary()

        assert "advanced_metrics" in summary
        assert summary["alerts"] == 1
        assert summary["warnings"] == 1

    def test_get_dashboard_summary_no_optimizer(self):
        """Test get_dashboard_summary when optimizer is not available."""
        self.mock_pool.optimizer = None
        self.mock_pool.performance_metrics = None
        self.mock_pool.get_basic_stats.return_value = {
            "counters": {
                "hits": 10,
                "misses": 5,
                "corrupted": 2,
                "creates": 10,
            }
        }
        summary = self.manager.get_dashboard_summary()

        assert "advanced_metrics" not in summary
        assert summary["alerts"] == 1  # Based on health issues
        assert summary["warnings"] == 0
