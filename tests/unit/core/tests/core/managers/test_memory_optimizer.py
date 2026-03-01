"""Tests for the MemoryOptimizer class."""

import logging
import time
from unittest.mock import ANY, Mock, patch

import pytest

from smartpool.config import MemoryConfig, MemoryConfigFactory, MemoryPreset
from smartpool.core.managers import MemoryOptimizer
from smartpool.core.utils import safe_log


# pylint: disable=R0903
class BaseMemoryOptimizerTest:
    """Base class for MemoryOptimizer tests, providing common setup."""

    # pylint: disable=W0201
    def setup_method(self):
        """Set up mock objects and MemoryOptimizer instance for each test."""
        self.mock_pool = Mock()
        self.mock_pool.current_preset = MemoryPreset.DEVELOPMENT
        self.mock_pool.default_config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        self.mock_pool.stats = Mock()
        self.optimizer = MemoryOptimizer(self.mock_pool)


# pylint: disable=protected-access
class TestMemoryOptimizerAutoTuning(BaseMemoryOptimizerTest):
    """Tests related to the auto-tuning functionality of MemoryOptimizer."""

    def test_enable_disable_auto_tuning(self):
        """Test enabling and disabling the auto-tuning feature."""
        assert not self.optimizer._auto_tune_enabled

        self.optimizer.enable_auto_tuning(interval_seconds=60)
        assert self.optimizer._auto_tune_enabled
        assert self.optimizer._auto_tune_interval == 60
        with patch("smartpool.core.managers.memory_optimizer.safe_log") as mock_safe_log:
            self.optimizer.enable_auto_tuning(interval_seconds=60)
            mock_safe_log.assert_called_once_with(self.optimizer.logger, logging.INFO, ANY)

        self.optimizer.disable_auto_tuning()
        assert not self.optimizer._auto_tune_enabled
        with patch("smartpool.core.managers.memory_optimizer.safe_log") as mock_safe_log:
            self.optimizer.disable_auto_tuning()
            mock_safe_log.assert_called_once_with(self.optimizer.logger, logging.INFO, ANY)

    def test_check_auto_tuning_disabled(self):
        """Test that check_auto_tuning does nothing when auto-tuning is disabled."""
        self.optimizer.disable_auto_tuning()
        with patch.object(self.optimizer, "perform_auto_tuning") as mock_perform:
            self.optimizer.check_auto_tuning()
            mock_perform.assert_not_called()

    def test_check_auto_tuning_interval_not_met(self):
        """Test that check_auto_tuning does nothing when interval is not met."""
        self.optimizer.enable_auto_tuning(interval_seconds=100)
        with patch.object(self.optimizer, "perform_auto_tuning") as mock_perform:
            self.optimizer.check_auto_tuning()
            mock_perform.assert_not_called()

    def test_check_auto_tuning_interval_met(self):
        """Test that check_auto_tuning performs tuning when interval is met."""
        initial_last_auto_tune = self.optimizer._last_auto_tune
        self.optimizer.enable_auto_tuning(interval_seconds=0.01)
        time.sleep(0.02)  # Wait for interval to pass
        with patch.object(self.optimizer, "perform_auto_tuning") as mock_perform:
            self.optimizer.check_auto_tuning()
            mock_perform.assert_called_once()
            assert self.optimizer._last_auto_tune > initial_last_auto_tune

    @patch("smartpool.core.managers.memory_optimizer.MemoryConfigFactory.auto_tune_config")
    def test_perform_auto_tuning_applies_changes(self, mock_auto_tune_config):
        """Test that auto-tuning applies significant configuration changes."""
        # Configure the mock to return a config with a larger max_objects_per_key
        tuned_config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        original_max_objects_per_key = tuned_config.max_objects_per_key
        tuned_config.max_objects_per_key = original_max_objects_per_key + 10
        mock_auto_tune_config.return_value = tuned_config

        # Mock metrics collection
        with patch.object(self.optimizer, "_collect_metrics") as mock_collect:
            mock_collect.return_value = {"hit_rate": 0.2}  # Low hit rate to trigger change

            applied = self.optimizer.perform_auto_tuning()

            assert applied
            # Verify that the pool's config was actually changed
            assert (
                self.mock_pool.default_config.max_objects_per_key
                == original_max_objects_per_key + 10
            )
            self.mock_pool.stats.increment.assert_called_once_with("auto_tune_adjustments")

    @patch("smartpool.core.managers.memory_optimizer.MemoryConfigFactory.auto_tune_config")
    def test_perform_auto_tuning_no_changes_no_increment(self, mock_auto_tune_config):
        """Test that auto-tuning does not increment stats if no changes are applied."""
        tuned_config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        mock_auto_tune_config.return_value = tuned_config  # Return same config, no changes

        with patch.object(self.optimizer, "_collect_metrics"):
            applied = self.optimizer.perform_auto_tuning()
            assert not applied
            self.mock_pool.stats.increment.assert_not_called()

    @patch("smartpool.core.managers.memory_optimizer.MemoryConfigFactory.auto_tune_config")
    def test_perform_auto_tuning_skips_minor_changes(self, mock_auto_tune_config):
        """Test that auto-tuning does not apply insignificant changes."""
        # Configure the mock to return a config with a tiny change
        tuned_config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        tuned_config.max_objects_per_key += 1  # Insignificant change
        mock_auto_tune_config.return_value = tuned_config

        with patch.object(self.optimizer, "_collect_metrics"):
            applied = self.optimizer.perform_auto_tuning()
            assert not applied
            self.mock_pool.stats.increment.assert_not_called()

    @patch("smartpool.core.managers.memory_optimizer.MemoryConfigFactory.auto_tune_config")
    def test_perform_auto_tuning_no_adjustments(self, mock_auto_tune_config):
        """
        Test that auto-tuning returns False and
        does not increment stats if no adjustments are made.
        """
        tuned_config = MemoryConfigFactory.create_preset(MemoryPreset.DEVELOPMENT)
        mock_auto_tune_config.return_value = tuned_config

        with patch.object(self.optimizer, "_collect_metrics"):
            with patch.object(
                self.optimizer, "_apply_config_changes", return_value={}
            ) as mock_apply_config_changes:
                applied = self.optimizer.perform_auto_tuning()
                assert not applied
                self.mock_pool.stats.increment.assert_not_called()
                mock_apply_config_changes.assert_called_once()

    @patch.object(
        MemoryOptimizer, "_collect_metrics", side_effect=TypeError("Collect Metrics Error")
    )
    # pylint: disable=W0613
    def test_perform_auto_tuning_exception_handling(self, mock_collect_metrics):
        """Test that perform_auto_tuning handles exceptions during metric collection."""
        with patch("smartpool.core.managers.memory_optimizer.safe_log") as mock_safe_log:
            applied = self.optimizer.perform_auto_tuning()
            assert not applied
            mock_safe_log.assert_called_once_with(self.optimizer.logger, logging.WARNING, ANY)


# pylint: disable=protected-access
class TestMemoryOptimizerAnalysisAndRecommendations(BaseMemoryOptimizerTest):
    """Tests related to optimization analysis and applying recommendations."""

    def test_force_optimization_analysis(self):
        """Test forcing an analysis and generating recommendations."""
        # Simulate a low hit rate
        with patch.object(self.optimizer, "_collect_metrics") as mock_collect:
            mock_collect.return_value = {"hit_rate": 0.25}
            analysis = self.optimizer.force_optimization_analysis()

            assert "recommendations" in analysis
            assert len(analysis["recommendations"]) > 0
            assert analysis["urgency_level"] == "critical"

            # Check for a specific recommendation
            rec = analysis["recommendations"][0]
            assert rec["parameter"] == "max_objects_per_key"
            assert rec["recommended"] > rec["current"]

    def test_force_optimization_analysis_medium_hit_rate(self):
        """Test forcing an analysis with a medium hit rate."""
        with patch.object(self.optimizer, "_collect_metrics") as mock_collect:
            mock_collect.return_value = {
                "hit_rate": 0.4,
                "avg_acquisition_time_ms": 5.0,
                "lock_contention_rate": 0.1,
            }
            analysis = self.optimizer.force_optimization_analysis()

            assert "recommendations" in analysis
            assert len(analysis["recommendations"]) == 1
            assert analysis["urgency_level"] == "warning"
            rec = analysis["recommendations"][0]
            assert rec["parameter"] == "max_objects_per_key"
            assert rec["type"] == "warning"

    def test_force_optimization_analysis_medium_contention(self):
        """Test forcing an analysis with medium lock contention."""
        with patch.object(self.optimizer, "_collect_metrics") as mock_collect:
            mock_collect.return_value = {
                "hit_rate": 0.8,
                "avg_acquisition_time_ms": 5.0,
                "lock_contention_rate": 0.3,
            }
            analysis = self.optimizer.force_optimization_analysis()

            assert "recommendations" in analysis
            assert len(analysis["recommendations"]) == 1
            assert analysis["urgency_level"] == "warning"
            rec = analysis["recommendations"][0]
            assert rec["parameter"] == "cleanup_interval_seconds"
            assert rec["type"] == "warning"

    def test_force_optimization_analysis_high_acquisition_time(self):
        """Test forcing an analysis with high acquisition time."""
        with patch.object(self.optimizer, "_collect_metrics") as mock_collect:
            mock_collect.return_value = {
                "hit_rate": 0.8,
                "avg_acquisition_time_ms": 25.0,
                "lock_contention_rate": 0.1,
            }
            analysis = self.optimizer.force_optimization_analysis()

            assert "recommendations" in analysis
            assert len(analysis["recommendations"]) == 1
            assert analysis["urgency_level"] == "warning"
            rec = analysis["recommendations"][0]
            assert rec["parameter"] == "max_validation_attempts"
            assert rec["type"] == "warning"

    def test_force_optimization_analysis_high_contention(self):
        """Test forcing an analysis with high lock contention."""
        with patch.object(self.optimizer, "_collect_metrics") as mock_collect:
            mock_collect.return_value = {
                "hit_rate": 0.8,
                "avg_acquisition_time_ms": 5.0,
                "lock_contention_rate": 0.5,
            }
            analysis = self.optimizer.force_optimization_analysis()

            assert "recommendations" in analysis
            assert len(analysis["recommendations"]) == 1
            assert analysis["urgency_level"] == "critical"
            rec = analysis["recommendations"][0]
            assert rec["parameter"] == "cleanup_interval_seconds"
            assert rec["type"] == "critical"

    def test_apply_recommendations(self):
        """Test applying a list of generated recommendations."""
        recommendations = [
            {
                "parameter": "max_objects_per_key",
                "recommended": 50,
                "current": 10,
                "reason": "Test",
            },
            {"parameter": "ttl_seconds", "recommended": 600, "current": 30, "reason": "Test"},
        ]

        with patch.object(self.optimizer, "_collect_metrics", return_value={}):
            result = self.optimizer.apply_recommendations(recommendations, confirm=True)

            assert result["status"] == "completed"
            assert len(result["applied"]) == 2
            assert self.mock_pool.default_config.max_objects_per_key == 50
            assert self.mock_pool.default_config.ttl_seconds == 600
            self.mock_pool.stats.increment.assert_called_once_with("manual_optimizations")

    def test_apply_recommendations_no_confirm(self):
        """Test apply_recommendations when confirm is False."""
        recommendations = [
            {"parameter": "max_objects_per_key", "recommended": 50, "current": 10, "reason": "Test"}
        ]
        result = self.optimizer.apply_recommendations(recommendations, confirm=False)
        assert result["status"] == "confirmation_required"
        assert result["recommendations_count"] == 1

    def test_apply_recommendations_with_failure(self):
        """Test apply_recommendations when one recommendation fails."""
        recommendations = [
            {
                "parameter": "max_objects_per_key",
                "recommended": 50,
                "current": 10,
                "reason": "Test",
            },
            {"parameter": "invalid_param", "recommended": 100, "current": 10, "reason": "Test"},
        ]
        with patch.object(self.optimizer, "_collect_metrics", return_value={}):
            result = self.optimizer.apply_recommendations(recommendations, confirm=True)
            assert result["status"] == "completed"
            assert len(result["applied"]) == 1
            assert len(result["failed"]) == 1
            assert result["failed"][0]["parameter"] == "invalid_param"
            assert result["success_rate"] > 0


# pylint: disable=protected-access
class TestMemoryOptimizerImprovementEstimation(BaseMemoryOptimizerTest):
    """Tests related to estimating improvement from recommendations."""

    def test_estimate_improvement_no_recommendations(self):
        """Test estimate_improvement when there are no recommendations."""
        result = self.optimizer._estimate_improvement([])
        assert result["overall"] == "No significant improvement expected"

    def test_estimate_improvement_high_impact(self):
        """Test estimate_improvement with high impact recommendations."""
        recommendations = [{"impact": "high"}, {"impact": "high"}]
        result = self.optimizer._estimate_improvement(recommendations)
        assert result["overall"] == "Major improvement expected"

    def test_estimate_improvement_medium_impact(self):
        """Test estimate_improvement with medium impact recommendations."""
        recommendations = [{"impact": "high"}, {"impact": "medium"}]
        result = self.optimizer._estimate_improvement(recommendations)
        assert result["overall"] == "Moderate improvement expected"

    def test_estimate_improvement_low_impact(self):
        """Test estimate_improvement with low impact recommendations."""
        recommendations = [{"impact": "low"}, {"impact": "low"}]
        result = self.optimizer._estimate_improvement(recommendations)
        assert result["overall"] == "Minor improvement expected"


class TestMemoryOptimizerTuningInfoAndHistory(BaseMemoryOptimizerTest):
    """Tests related to tuning information and adjustment history."""

    def test_get_tuning_info(self):
        """Test the structure of the tuning info report."""
        self.optimizer.enable_auto_tuning(interval_seconds=120)
        info = self.optimizer.get_tuning_info()

        assert info["enabled"]
        assert info["interval"] == 120
        assert "last_run" in info
        assert "history" in info

    def test_get_tuning_info_no_auto_tune(self):
        """Test get_tuning_info when auto-tuning is not enabled."""
        self.optimizer.disable_auto_tuning()
        info = self.optimizer.get_tuning_info()
        assert not info["enabled"]
        assert info["next_run_in"] is None

    # pylint: disable=protected-access
    def test_record_adjustment_history_limit(self):
        """Test that _record_adjustment limits the history size."""
        self.optimizer._max_history_size = 2
        self.optimizer._record_adjustment(
            {"max_objects_per_key": {"from": 10, "to": 20}}, {"hit_rate": 0.5}
        )
        self.optimizer._record_adjustment(
            {"max_objects_per_key": {"from": 20, "to": 30}}, {"hit_rate": 0.6}
        )
        self.optimizer._record_adjustment(
            {"max_objects_per_key": {"from": 30, "to": 40}}, {"hit_rate": 0.7}
        )

        assert len(self.optimizer._adjustment_history) == 2
        assert (
            self.optimizer._adjustment_history[0]["adjustments"]["max_objects_per_key"]["from"]
            == 20
        )


# pylint: disable=protected-access
class TestMemoryOptimizerMetricCollection(BaseMemoryOptimizerTest):
    """Tests related to metric collection within MemoryOptimizer."""

    def test_collect_metrics_with_performance_metrics(self):
        """Test _collect_metrics when performance_metrics are available."""
        self.mock_pool.performance_metrics = Mock()
        self.mock_pool.performance_metrics.create_snapshot.return_value = Mock(
            hit_rate=0.9, avg_acquisition_time_ms=1.5, lock_contention_rate=0.05
        )
        metrics = self.optimizer._collect_metrics()
        assert metrics["hit_rate"] == 0.9
        assert metrics["avg_acquisition_time_ms"] == 1.5
        assert metrics["lock_contention_rate"] == 0.05

    def test_collect_metrics_without_performance_metrics(self):
        """Test _collect_metrics when performance_metrics are not available."""
        self.mock_pool.performance_metrics = None
        self.mock_pool.get_basic_stats.return_value = {"counters": {"hits": 90, "misses": 10}}
        metrics = self.optimizer._collect_metrics()
        assert metrics["hit_rate"] == pytest.approx(0.9)
        assert metrics["avg_acquisition_time_ms"] == 5.0
        assert metrics["lock_contention_rate"] == 0.1

    def test_collect_metrics_without_performance_metrics_no_requests(self):
        """Test _collect_metrics when no hits or misses are recorded."""
        self.mock_pool.performance_metrics = None
        self.mock_pool.get_basic_stats.return_value = {"counters": {"hits": 0, "misses": 0}}
        metrics = self.optimizer._collect_metrics()
        assert metrics["hit_rate"] == 0


# pylint: disable=protected-access
class TestMemoryOptimizerConfigChanges(BaseMemoryOptimizerTest):
    """Tests related to applying configuration changes within MemoryOptimizer."""

    def test_apply_config_changes_max_objects_per_key(self):
        """Test _apply_config_changes for max_objects_per_key."""
        tuned_config = MemoryConfig()
        tuned_config.max_objects_per_key = self.mock_pool.default_config.max_objects_per_key + 5

        with patch.object(
            self.optimizer, "_collect_metrics", return_value={"lock_contention_rate": 0.1}
        ):
            adjustments = self.optimizer._apply_config_changes(tuned_config)
            assert "max_objects_per_key" in adjustments
            assert (
                self.mock_pool.default_config.max_objects_per_key
                == tuned_config.max_objects_per_key
            )

    def test_apply_config_changes_ttl_seconds(self):
        """Test _apply_config_changes for ttl_seconds."""
        tuned_config = MemoryConfig()
        tuned_config.ttl_seconds = (
            self.mock_pool.default_config.ttl_seconds + 60
        )  # Significant change

        with patch.object(
            self.optimizer, "_collect_metrics", return_value={"lock_contention_rate": 0.1}
        ):
            adjustments = self.optimizer._apply_config_changes(tuned_config)
            assert "ttl_seconds" in adjustments
            assert self.mock_pool.default_config.ttl_seconds == tuned_config.ttl_seconds

    def test_apply_config_changes_cleanup_interval_seconds_high_contention(self):
        """Test _apply_config_changes for cleanup_interval_seconds with high contention."""
        tuned_config = MemoryConfig()
        tuned_config.cleanup_interval_seconds = (
            self.mock_pool.default_config.cleanup_interval_seconds * 2
        )

        with patch.object(
            self.optimizer, "_collect_metrics", return_value={"lock_contention_rate": 0.4}
        ):
            adjustments = self.optimizer._apply_config_changes(tuned_config)
            assert "cleanup_interval_seconds" in adjustments
            assert (
                self.mock_pool.default_config.cleanup_interval_seconds
                == tuned_config.cleanup_interval_seconds
            )

    def test_apply_config_changes_cleanup_interval_seconds_low_contention(self):
        """Test _apply_config_changes for cleanup_interval_seconds with low contention."""
        tuned_config = MemoryConfig()
        tuned_config.cleanup_interval_seconds = (
            self.mock_pool.default_config.cleanup_interval_seconds * 2
        )

        with patch.object(
            self.optimizer, "_collect_metrics", return_value={"lock_contention_rate": 0.1}
        ):
            adjustments = self.optimizer._apply_config_changes(tuned_config)
            assert "cleanup_interval_seconds" not in adjustments
            # Should not change if contention is low
            assert (
                self.mock_pool.default_config.cleanup_interval_seconds
                != tuned_config.cleanup_interval_seconds
            )


class TestSafeLogUtility:
    """Tests for the safe_log utility function."""

    # pylint: disable=W0201
    def setup_method(self):
        """Set up a mock logger for safe_log tests."""
        self.mock_logger = Mock()
        self.mock_logger.isEnabledFor.return_value = True

    def test_safe_log_handles_exceptions(self):
        """Test that safe_log handles exceptions gracefully."""
        self.mock_logger.log.side_effect = ValueError("Test Error")
        safe_log(self.mock_logger, 20, "Test message")
        self.mock_logger.log.assert_called_once_with(20, "Test message")

    def test_safe_log_handles_oserror(self):
        """Test that safe_log handles OSError gracefully."""
        self.mock_logger.log.side_effect = OSError("Test OSError")
        safe_log(self.mock_logger, 20, "Test message")
        self.mock_logger.log.assert_called_once_with(20, "Test message")

    def test_safe_log_handles_generic_exception(self):
        """Test that safe_log handles generic Exception gracefully."""
        self.mock_logger.log.side_effect = Exception("Test Generic Exception")
        safe_log(self.mock_logger, 20, "Test message")
        self.mock_logger.log.assert_called_once_with(20, "Test message")

    def test_safe_log_no_logger(self):
        """Test safe_log when logger is None."""
        safe_log(None, 20, "Test message")
        # No exception should be raised

    def test_safe_log_logger_not_enabled(self):
        """Test safe_log when logger is not enabled for the level."""
        self.mock_logger.isEnabledFor.return_value = False
        safe_log(self.mock_logger, 20, "Test message")
        self.mock_logger.log.assert_not_called()
