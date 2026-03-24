"""
Memory optimization module for adaptive object management.

This module provides automatic optimization and tuning capabilities for memory pools,
enabling dynamic adjustment of pool parameters based on performance metrics to maintain
optimal performance under varying workloads.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict

from smartpool.config import MemoryConfig, MemoryConfigFactory
from smartpool.core.utils import safe_log

if TYPE_CHECKING:  # pragma: no cover
    from smartpool.core.smartpool_manager import SmartObjectManager


class MemoryOptimizer:
    """
    Manages the automatic optimization and tuning of the memory pool's configuration
    based on observed performance metrics. This class enables dynamic adjustment of
    pool parameters to maintain optimal performance under varying workloads.

    Responsibilities:
        - Periodically collecting performance metrics and analyzing them.
        - Dynamically adjusting pool configuration parameters
          (e.g., `max_objects_per_key`, `ttl_seconds`) to improve hit rate,
          reduce acquisition times, and mitigate lock contention.
        - Providing optimization recommendations to the user.
        - Maintaining a history of adjustments made.
    """

    def __init__(self, pool: "SmartObjectManager"):
        """
        Initializes the MemoryOptimizer.

        Args:
            pool (SmartObjectManager): A reference to the main memory pool, used to access
                                      its configuration, metrics, and statistics.
        """
        self.pool = pool
        self.logger = logging.getLogger(__name__)

        # Flag indicating whether auto-tuning is currently enabled.
        self._auto_tune_enabled = False
        # The interval (in seconds) at which auto-tuning analysis and adjustments are performed.
        self._auto_tune_interval = 300.0  # 5 minutes by default
        # The timestamp of the last auto-tuning execution.
        self._last_auto_tune = time.time()

        # A list to store a history of adjustments made by the optimizer.
        self._adjustment_history: list = []
        # The maximum number of adjustment records to keep in history.
        self._max_history_size = 50

    def enable_auto_tuning(self, interval_seconds: float = 300.0) -> None:
        """Enables periodic auto-tuning"""
        self._auto_tune_enabled = True
        self._auto_tune_interval = interval_seconds
        self._last_auto_tune = time.time()
        safe_log(
            self.logger, logging.INFO, f"Auto-tuning enabled with {interval_seconds}s interval"
        )

    def disable_auto_tuning(self) -> None:
        """Disables auto-tuning"""
        self._auto_tune_enabled = False
        safe_log(self.logger, logging.INFO, "Auto-tuning disabled")

    def check_auto_tuning(self) -> None:
        """Checks if auto-tuning should be executed"""
        if not self._auto_tune_enabled:
            return

        current_time = time.time()
        if current_time - self._last_auto_tune >= self._auto_tune_interval:
            self.perform_auto_tuning()
            self._last_auto_tune = current_time

    def _perform_adjustments(
        self, tuned_config: MemoryConfig, observed_metrics: Dict[str, float]
    ) -> bool:
        """
        Performs auto-tuning based on metrics.

        Returns:
            True if adjustments were made
        """
        # Apply changes if significant
        adjustments = self._apply_config_changes(tuned_config)

        if adjustments:
            self._record_adjustment(adjustments, observed_metrics)
            self.pool.stats.increment("auto_tune_adjustments")
            return True

        return False

    def perform_auto_tuning(self) -> bool:
        """
        Performs auto-tuning based on metrics.

        Returns:
            True if adjustments were made
        """
        try:
            observed_metrics = self._collect_metrics()

            # Get an optimized configuration
            tuned_config = MemoryConfigFactory.auto_tune_config(
                self.pool.default_config, observed_metrics
            )

            return self._perform_adjustments(tuned_config, observed_metrics)
        except (AttributeError, ValueError, TypeError, KeyError) as e:
            safe_log(self.logger, logging.WARNING, f"Auto-tuning failed: {e}")
            return False

    def _collect_metrics(self) -> Dict[str, float]:
        """Collects current metrics for auto-tuning"""
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            return {
                "hit_rate": snapshot.hit_rate,
                "avg_acquisition_time_ms": snapshot.avg_acquisition_time_ms,
                "lock_contention_rate": snapshot.lock_contention_rate,
            }
        # Use basic pool stats
        stats = self.pool.get_basic_stats()
        counters = stats.get("counters", {})
        hits = counters.get("hits", 0)
        misses = counters.get("misses", 0)
        total_requests = hits + misses
        hit_rate = hits / total_requests if total_requests > 0 else 0

        return {
            "hit_rate": hit_rate,
            "avg_acquisition_time_ms": 5.0,  # Conservative default value
            "lock_contention_rate": 0.1,  # Conservative default value
        }

    def _apply_config_changes(self, tuned_config: MemoryConfig) -> Dict[str, Any]:
        """Applies configuration changes and returns adjustments"""
        adjustments = {}

        # Check and apply max_objects_per_key
        if abs(tuned_config.max_objects_per_key - self.pool.default_config.max_objects_per_key) > 2:
            old_size = self.pool.default_config.max_objects_per_key
            self.pool.default_config.max_objects_per_key = tuned_config.max_objects_per_key
            adjustments["max_objects_per_key"] = {
                "from": old_size,
                "to": tuned_config.max_objects_per_key,
            }

            safe_log(
                self.logger,
                logging.INFO,
                f"Auto-tuning: max_objects_per_key {old_size}"
                f" -> {tuned_config.max_objects_per_key}",
            )

        # Check and apply ttl_seconds
        if abs(tuned_config.ttl_seconds - self.pool.default_config.ttl_seconds) > 30:
            old_ttl = self.pool.default_config.ttl_seconds
            self.pool.default_config.ttl_seconds = tuned_config.ttl_seconds
            adjustments["ttl_seconds"] = {
                "from": int(old_ttl),
                "to": int(tuned_config.ttl_seconds),
            }

            safe_log(
                self.logger,
                logging.INFO,
                f"Auto-tuning: ttl_seconds {old_ttl} -> {tuned_config.ttl_seconds}",
            )

        # Check and apply cleanup_interval_seconds if contention is high
        current_metrics = self._collect_metrics()
        if current_metrics.get("lock_contention_rate", 0) > 0.3:
            if (
                tuned_config.cleanup_interval_seconds
                != self.pool.default_config.cleanup_interval_seconds
            ):
                old_interval = self.pool.default_config.cleanup_interval_seconds
                self.pool.default_config.cleanup_interval_seconds = (
                    tuned_config.cleanup_interval_seconds
                )
                adjustments["cleanup_interval_seconds"] = {
                    "from": int(old_interval),
                    "to": int(tuned_config.cleanup_interval_seconds),
                }

                safe_log(
                    self.logger,
                    logging.INFO,
                    (
                        f"Auto-tuning: cleanup_interval_seconds {old_interval}"
                        f" -> {tuned_config.cleanup_interval_seconds}"
                    ),
                )

        return adjustments

    def _record_adjustment(self, adjustments: Dict[str, Any], metrics: Dict[str, float]) -> None:
        """Records an adjustment in the history"""
        record = {
            "timestamp": time.time(),
            "adjustments": adjustments,
            "triggering_metrics": metrics.copy(),
            "preset": self.pool.current_preset.value,
        }

        self._adjustment_history.append(record)

        # Limit history size
        if len(self._adjustment_history) > self._max_history_size:
            self._adjustment_history.pop(0)

    def get_tuning_info(self) -> Dict[str, Any]:
        """Returns auto-tuning information"""
        return {
            "enabled": self._auto_tune_enabled,
            "interval": self._auto_tune_interval,
            "last_run": self._last_auto_tune,
            "adjustments_count": self.pool.stats.get("auto_tune_adjustments"),
            "history": self._adjustment_history[-10:],  # 10 derniers ajustements
            "next_run_in": (
                max(0, self._auto_tune_interval - (time.time() - self._last_auto_tune))
                if self._auto_tune_enabled
                else None
            ),
        }

    def force_optimization_analysis(self) -> Dict[str, Any]:
        """Forces an optimization analysis and returns recommendations"""
        metrics = self._collect_metrics()
        current_config = self.pool.default_config

        recommendations = []
        urgency_score = 0

        # Analyze hit rate
        hit_rate = metrics.get("hit_rate", 0)
        if hit_rate < 0.3:
            recommendations.append(
                {
                    "type": "critical",
                    "parameter": "max_objects_per_key",
                    "current": current_config.max_objects_per_key,
                    "recommended": min(current_config.max_objects_per_key * 2, 200),
                    "reason": f"Very low hit rate ({hit_rate:.1%}). Double pool size.",
                    "impact": "high",
                }
            )
            urgency_score += 3
        elif hit_rate < 0.6:
            recommendations.append(
                {
                    "type": "warning",
                    "parameter": "max_objects_per_key",
                    "current": current_config.max_objects_per_key,
                    "recommended": int(current_config.max_objects_per_key * 1.5),
                    "reason": f"Suboptimal hit rate ({hit_rate:.1%}). Increase pool size.",
                    "impact": "medium",
                }
            )
            urgency_score += 1

        # Analyze acquisition times
        avg_time = metrics.get("avg_acquisition_time_ms", 0)
        if avg_time > 20.0:
            recommendations.append(
                {
                    "type": "warning",
                    "parameter": "max_validation_attempts",
                    "current": current_config.max_validation_attempts,
                    "recommended": max(1, current_config.max_validation_attempts - 1),
                    "reason": (
                        f"High acquisition time ({avg_time:.1f}ms). Reduce validation attempts."
                    ),
                    "impact": "medium",
                }
            )
            urgency_score += 1

        # Analyze contention
        contention = metrics.get("lock_contention_rate", 0)
        if contention > 0.4:
            recommendations.append(
                {
                    "type": "critical",
                    "parameter": "cleanup_interval_seconds",
                    "current": current_config.cleanup_interval_seconds,
                    "recommended": current_config.cleanup_interval_seconds * 2,
                    "reason": f"Very high contention ({contention:.1%}). Reduce cleanup frequency.",
                    "impact": "high",
                }
            )
            urgency_score += 3
        elif contention > 0.25:
            recommendations.append(
                {
                    "type": "warning",
                    "parameter": "cleanup_interval_seconds",
                    "current": current_config.cleanup_interval_seconds,
                    "recommended": current_config.cleanup_interval_seconds * 1.5,
                    "reason": f"High contention ({contention:.1%}). Adjust cleanup frequency.",
                    "impact": "medium",
                }
            )
            urgency_score += 1

        return {
            "current_metrics": metrics,
            "urgency_score": urgency_score,
            "urgency_level": (
                "critical" if urgency_score >= 3 else "warning" if urgency_score >= 1 else "info"
            ),
            "recommendations": recommendations,
            "estimated_improvement": self._estimate_improvement(recommendations),
        }

    def _estimate_improvement(self, recommendations: list) -> Dict[str, str]:
        """Estimates the expected improvement from recommendations"""
        if not recommendations:
            return {"overall": "No significant improvement expected"}

        high_impact_count = sum(1 for r in recommendations if r["impact"] == "high")
        medium_impact_count = sum(1 for r in recommendations if r["impact"] == "medium")

        if high_impact_count >= 2:
            return {
                "overall": "Major improvement expected",
                "hit_rate": "+20-40%",
                "response_time": "-30-50%",
                "throughput": "+25-50%",
            }
        if high_impact_count == 1 or medium_impact_count >= 2:
            return {
                "overall": "Moderate improvement expected",
                "hit_rate": "+10-20%",
                "response_time": "-15-30%",
                "throughput": "+10-25%",
            }
        return {
            "overall": "Minor improvement expected",
            "hit_rate": "+5-10%",
            "response_time": "-5-15%",
            "throughput": "+5-15%",
        }

    def apply_recommendations(self, recommendations: list, confirm: bool = False) -> Dict[str, Any]:
        """
        Applies a list of recommendations.

        Args:
            recommendations: List of recommendations to apply
            confirm: If True, applies without asking for confirmation

        Returns:
            Application result
        """
        if not confirm:
            return {
                "status": "confirmation_required",
                "message": "Use confirm=True to apply recommendations",
                "recommendations_count": len(recommendations),
            }

        applied = []
        failed = []

        for rec in recommendations:
            try:
                param = rec["parameter"]
                new_value = rec["recommended"]
                old_value = getattr(self.pool.default_config, param)

                # Apply the change
                setattr(self.pool.default_config, param, new_value)

                applied.append(
                    {
                        "parameter": param,
                        "from": old_value,
                        "to": new_value,
                        "reason": rec["reason"],
                    }
                )

                safe_log(
                    self.logger,
                    logging.INFO,
                    f"Applied recommendation: {param} {old_value} -> {new_value}",
                )

            except (AttributeError, ValueError, TypeError) as e:
                failed.append({"parameter": rec["parameter"], "error": str(e)})
                safe_log(
                    self.logger,
                    logging.ERROR,
                    f"Failed to apply recommendation for {rec['parameter']}: {e}",
                )

        # Record manual application
        if applied:
            self._record_adjustment({"manual_application": applied}, self._collect_metrics())
            self.pool.stats.increment("manual_optimizations")

        return {
            "status": "completed",
            "applied": applied,
            "failed": failed,
            "success_rate": (len(applied) / len(recommendations) if recommendations else 0),
        }
