"""
Memory Manager module for adaptive object pool management.

This module provides the MemoryManager class which acts as a high-level facade
for managing memory pool operations, configuration presets, performance monitoring,
and optimization recommendations.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, TypedDict

from smartpool.config import MemoryConfig, MemoryConfigFactory, MemoryPreset
from smartpool.core.metrics import (
    PerformanceMetrics,
    PerformanceSnapshot,
)
from smartpool.core.utils import safe_log

if TYPE_CHECKING:  # pragma: no cover
    from smartpool.core.smartpool_manager import SmartObjectManager


class ObjectInfoPooled(TypedDict):
    """ObjectInfoPooled typed dict"""

    age_seconds: float
    access_count: int
    time_since_last_access: float
    state: str
    size_bytes: int


class ObjectInfoActive(TypedDict):
    """ObjectInfoActive typed dict"""

    obj_id: int
    age_seconds: float
    access_count: int
    size_bytes: int


class KeyData(TypedDict):
    """KeyData typed dict"""

    total_pooled_objects: List[ObjectInfoPooled]
    active_objects_count: List[ObjectInfoActive]
    pooled_count: int
    active_count: int
    pooled_memory: int
    active_memory: int


class MemoryManager:
    """
    Manages high-level operations for the memory pool, including handling configuration presets,
    generating comprehensive performance reports, and providing optimization recommendations.
    It acts as a facade for various underlying pool components, offering a unified interface
    for pool administration and monitoring.

    Responsibilities:
    - Managing and switching between predefined pool configuration presets.
    - Generating detailed performance and health reports based on collected metrics.
    - Comparing current pool configuration with presets and suggesting optimal configurations.
    - Providing a high-level interface for overall pool management and monitoring.
    """

    def __init__(self, pool: "SmartObjectManager"):
        """
        Initializes the MemoryManager with a reference to the main SmartObjectManager.

        Args:
            pool (SmartObjectManager): The instance of the SmartObjectManager
                    that this manager will control.
        """
        self.pool = pool
        self.logger = logging.getLogger(__name__)

        # The current configuration preset applied to the pool.
        self.current_preset = pool.current_preset

    def get_performance_report(self, detailed: bool = True) -> Dict[str, Any]:
        """
        Generates a comprehensive performance report for the memory pool.
        This report includes basic statistics, auto-tuning information, and optionally
        detailed performance metrics and per-key statistics.

        Args:
            detailed (bool): If True, the report will include advanced performance metrics
                             and per-key statistics, provided `enable_performance_metrics`
                             is enabled in the pool's configuration.

        Returns:
            Dict[str, Any]: A structured dictionary containing the performance report.
        """
        basic_stats = self.pool.get_basic_stats()

        # Basic information always present in the report.
        base_report = {
            "basic_stats": basic_stats,
            "preset": self.current_preset.value,
            "config": {
                "max_objects_per_key": self.pool.default_config.max_objects_per_key,
                "ttl_seconds": self.pool.default_config.ttl_seconds,
                "cleanup_interval_seconds": self.pool.default_config.cleanup_interval_seconds,
                "max_expected_concurrency": self.pool.default_config.max_expected_concurrency,
                "object_creation_cost": self.pool.default_config.object_creation_cost,
                "memory_pressure": self.pool.default_config.memory_pressure,
            },
        }

        # Include auto-tuning information if the optimizer is available.
        if hasattr(self.pool, "optimizer") and self.pool.optimizer:
            base_report["auto_tuning"] = self.pool.optimizer.get_tuning_info()
        else:
            base_report["auto_tuning"] = {
                "enabled": False,
                "interval": 0,
                "last_run": 0,
                "adjustments_count": 0,
            }

        # Add advanced metrics if enabled and requested.
        if self.pool.performance_metrics and detailed:
            perf_report = self.pool.performance_metrics.get_performance_report()
            key_stats = self.pool.performance_metrics.get_key_statistics()

            base_report.update({"performance": perf_report, "key_statistics": key_stats})

        return base_report

    def get_preset_info(self) -> Dict[str, Any]:
        """
        Retrieves detailed information about all available pool configuration presets,
        including their descriptions and a comparison of the current configuration
        against each preset.

        Returns:
            Dict[str, Any]: A dictionary containing:
                        - 'current_preset': The name of the currently active preset.
                        - 'description': A description of the current preset.
                        - 'available_presets': A mapping of all preset names to their descriptions.
                        - 'preset_comparison': A detailed comparison of the current configuration
                                            with each available preset, including estimated impacts.
        """
        recommendations = MemoryConfigFactory.get_preset_recommendations()

        return {
            "current_preset": self.current_preset.value,
            "description": recommendations.get(self.current_preset, "Custom configuration"),
            "available_presets": {preset.value: desc for preset, desc in recommendations.items()},
            "preset_comparison": self._compare_with_presets(),
        }

    def _compare_with_presets(self) -> Dict[str, Any]:
        """
        Compares the pool's current configuration with each of the predefined presets
        and estimates the impact of switching to them. This helps in making informed
        decisions about configuration changes.

        Returns:
            Dict[str, Any]: A dictionary where keys are preset names and values are
                            dictionaries detailing the differences in `max_objects_per_key`
                            and `ttl_seconds`, along with estimated impacts
                            on performance and memory.
        """
        comparisons = {}
        current_snapshot = None

        if self.pool.performance_metrics:
            current_snapshot = self.pool.performance_metrics.create_snapshot()

        for preset in MemoryPreset:
            if preset == MemoryPreset.CUSTOM:
                continue

            preset_config = MemoryConfigFactory.create_preset(preset)

            comparison = {
                "max_objects_per_key_diff": preset_config.max_objects_per_key
                - self.pool.default_config.max_objects_per_key,
                "ttl_diff": preset_config.ttl_seconds - self.pool.default_config.ttl_seconds,
                "expected_impact": self._estimate_preset_impact(preset_config, current_snapshot),
                "memory_impact": self._estimate_memory_impact(preset_config),
                "performance_impact": self._estimate_performance_impact(preset_config),
            }

            comparisons[preset.value] = comparison

        return comparisons

    def _estimate_preset_impact(
        self, preset_config: MemoryConfig, current_snapshot: Optional[PerformanceSnapshot]
    ) -> str:
        """
        Estimates the overall impact of changing to a specific preset based on configuration
        differences and current performance metrics.

        Args:
            preset_config (PoolConfig): The configuration of the preset being considered.
            current_snapshot (Optional[PerformanceSnapshot]):
                        The current performance snapshot of the pool.

        Returns:
            str: A descriptive string summarizing the estimated impact.
        """
        if not current_snapshot:
            return "Unknown impact"

        # Simplified impact analysis based on max_objects_per_key and current hit rate.
        if preset_config.max_objects_per_key > self.pool.default_config.max_objects_per_key:
            if hasattr(current_snapshot, "hit_rate") and current_snapshot.hit_rate < 0.6:
                return "Probable improvement in hit rate and performance"
            return "Increased memory consumption without significant gain"
        if preset_config.max_objects_per_key < self.pool.default_config.max_objects_per_key:
            return "Memory reduction but possible performance degradation"
        return "Limited impact on performance"

    def _estimate_memory_impact(self, preset_config: MemoryConfig) -> str:
        """
        Estimates the memory impact of applying a given preset configuration.

        Args:
            preset_config (PoolConfig): The configuration of the preset being considered.

        Returns:
            str: A descriptive string indicating the estimated memory impact.
        """
        size_diff = preset_config.max_objects_per_key - self.pool.default_config.max_objects_per_key

        if size_diff > 20:
            return f"+{size_diff} max objects (high memory impact)"
        if size_diff > 5:
            return f"+{size_diff} max objects (moderate memory impact)"
        if size_diff < -5:
            return f"{size_diff} max objects (memory reduction)"
        return "Negligible memory impact"

    def _estimate_performance_impact(self, preset_config: MemoryConfig) -> str:
        """
        Estimates the performance impact of applying a given preset configuration.

        Args:
            preset_config (PoolConfig): The configuration of the preset being considered.

        Returns:
            str: A descriptive string indicating the estimated performance impact.
        """
        current_stats = self.pool.get_basic_stats()
        total_requests = current_stats.get("creates", 0) + current_stats.get("reuses", 0)
        hit_rate = current_stats.get("reuses", 0) / max(1, total_requests)

        if (
            preset_config.max_objects_per_key > self.pool.default_config.max_objects_per_key
            and hit_rate < 0.7
        ):
            return "Expected improvement in hit rate and throughput"
        if preset_config.ttl_seconds > self.pool.default_config.ttl_seconds:
            return "Increased reuse, fewer object creations"
        if preset_config.max_validation_attempts < self.pool.default_config.max_validation_attempts:
            return "Reduced acquisition times, faster validation"
        return "Neutral performance impact"

    def switch_preset(self, new_preset: MemoryPreset) -> Dict[str, Any]:
        """
        Changes the current configuration preset of the memory pool.
        This method applies the parameters defined by the new preset to the pool's
        default configuration and reconfigures performance metrics if necessary.

        Args:
            new_preset (MemoryPreset): The new preset to apply to the pool.

        Returns:
            Dict[str, Any]: A report detailing the success of the operation,
                        the old and new presets, and a dictionary of specific configuration
                        changes that were applied.
        """
        old_preset = self.current_preset
        new_config = MemoryConfigFactory.create_preset(new_preset)

        # Capture relevant state before applying changes for reporting.
        old_state = {
            "max_objects_per_key": self.pool.default_config.max_objects_per_key,
            "ttl_seconds": self.pool.default_config.ttl_seconds,
            "cleanup_interval_seconds": self.pool.default_config.cleanup_interval_seconds,
        }

        with self.pool.lock:
            self.pool._shutdown_metrics_dispatcher(  # pylint: disable=protected-access
                self.pool.default_config.metrics_flush_timeout_seconds
            )

            # Apply the new configuration to the pool.
            self.pool.default_config = new_config
            self.current_preset = new_preset
            self.pool.current_preset = new_preset  # Update the pool's internal current_preset

            # Reconfigure performance metrics manager based on the new preset's settings.
            if self.pool.performance_metrics:
                if not new_config.enable_performance_metrics:
                    self.pool.performance_metrics = None
                    safe_log(
                        self.logger,
                        logging.INFO,
                        "Performance metrics disabled due to preset change",
                    )
            elif new_config.enable_performance_metrics:
                self.pool.performance_metrics = PerformanceMetrics(
                    history_size=new_config.max_performance_history_size,
                    enable_detailed_tracking=new_config.enable_acquisition_tracking,
                )
                safe_log(
                    self.logger, logging.INFO, "Performance metrics enabled due to preset change"
                )

            self.pool._initialize_metrics_dispatcher()  # pylint: disable=protected-access

        # Capture state after applying changes.
        new_state = {
            "max_objects_per_key": self.pool.default_config.max_objects_per_key,
            "ttl_seconds": self.pool.default_config.ttl_seconds,
            "cleanup_interval_seconds": self.pool.default_config.cleanup_interval_seconds,
        }

        # Log the configuration change.
        safe_log(
            self.logger,
            logging.INFO,
            f"Switched preset from {old_preset.value} to {new_preset.value}. "
            f"max_objects_per_key: {old_state['max_objects_per_key']}"
            f" -> {new_state['max_objects_per_key']}, "
            f"ttl: {old_state['ttl_seconds']} -> {new_state['ttl_seconds']}",
        )

        return {
            "success": True,
            "old_preset": old_preset.value,
            "new_preset": new_preset.value,
            "changes": {
                key: {"from": old_state[key], "to": new_state[key]}
                for key in old_state  # pylint: disable=consider-using-dict-items
                if old_state[key] != new_state[key]
            },
        }

    def get_detailed_stats(self) -> Dict[str, Any]:
        """
        Retrieves detailed statistics about the pool, including a breakdown of pooled and
        active objects per key, memory usage, and configuration details for each key.

        Returns:
            Dict[str, Any]: A comprehensive dictionary containing:
                            - 'general': Basic pool statistics.
                            - 'by_key': Detailed statistics for each unique object key.
                            - 'total_memory_bytes': Total estimated memory consumed by all objects.
                            - 'history': A list of recent historical metric snapshots.
        """
        with self.pool.lock:
            current_time = time.time()
            aggregated_key_data: Dict[str, KeyData] = {}

            # Process pooled objects to gather their statistics.
            for key, queue in self.pool.pool.items():
                if key not in aggregated_key_data:
                    aggregated_key_data[key] = {
                        "total_pooled_objects": [],
                        "active_objects_count": [],
                        "active_count": 0,
                        "active_memory": 0,
                        "pooled_count": 0,
                        "pooled_memory": 0,
                    }
                for pooled_obj in queue:
                    age = current_time - pooled_obj.created_at
                    aggregated_key_data[key]["pooled_memory"] += pooled_obj.estimated_size
                    aggregated_key_data[key]["pooled_count"] += 1
                    aggregated_key_data[key]["total_pooled_objects"].append(
                        {
                            "age_seconds": age,
                            "access_count": pooled_obj.access_count,
                            "time_since_last_access": current_time - pooled_obj.last_accessed,
                            "state": pooled_obj.state.value,
                            "size_bytes": pooled_obj.estimated_size,
                        }
                    )

            # Process active objects by retrieving information from the active manager.
            active_objects_count_info = self.pool.active_manager.get_active_objects_count_info()

            for obj_id, obj_info in active_objects_count_info.items():
                key = obj_info.key

                if key not in aggregated_key_data:
                    aggregated_key_data[key] = {
                        "total_pooled_objects": [],
                        "active_objects_count": [],
                        "pooled_count": 0,
                        "active_count": 0,
                        "pooled_memory": 0,
                        "active_memory": 0,
                    }

                aggregated_key_data[key]["active_memory"] += obj_info.estimated_size
                aggregated_key_data[key]["active_count"] += 1

                age = current_time - obj_info.created_at
                aggregated_key_data[key]["active_objects_count"].append(
                    {
                        "obj_id": obj_id,
                        "age_seconds": age,
                        "access_count": obj_info.access_count,
                        "size_bytes": obj_info.estimated_size,
                    }
                )

            # Consolidate and build the final statistics by key.
            key_stats = {}
            total_memory = 0
            for key, data in aggregated_key_data.items():
                total_memory_for_key = data["pooled_memory"] + data["active_memory"]
                total_memory += total_memory_for_key

                key_stats[key] = {
                    "pooled_count": data["pooled_count"],
                    "active_count": data["active_count"],
                    "total_count": data["pooled_count"] + data["active_count"],
                    "last_access": self.pool.operations_manager.get_lru_stats().get(key, 0),
                    "config": {
                        "max_objects_per_key": self.pool.get_config_for_key(
                            key
                        ).max_objects_per_key,
                        "ttl_seconds": self.pool.get_config_for_key(key).ttl_seconds,
                    },
                    "memory_bytes": total_memory_for_key,
                    "corrupted_count": self.pool.operations_manager.get_corruption_stats().get(
                        key, 0
                    ),
                    "total_pooled_objects": data["total_pooled_objects"],
                    "active_objects_count": data["active_objects_count"],
                }

            return {
                "general": self.pool.get_basic_stats(),
                "by_key": key_stats,
                "total_memory_bytes": total_memory,
                "history": [m.to_dict() for m in self.pool.stats.get_history(last_n=10)],
            }

    @property
    def total_memory(self) -> int:
        """Memory used by the pool."""
        return self._calculate_total_memory()

    def _calculate_total_memory(self) -> int:
        """Calculate the total memory off all objects (pooled and actives)."""
        with self.pool.lock:
            total_memory = 0

            for queue in self.pool.pool.values():
                for pooled_obj in queue:
                    total_memory += pooled_obj.estimated_size

            active_objects_info = self.pool.active_manager.get_active_objects_count_info()
            for obj_info in active_objects_info.values():
                total_memory += obj_info.estimated_size

            return total_memory

    def get_optimization_recommendations(self) -> Dict[str, Any]:
        """
        Generates optimization recommendations for the pool based on its
        current state and observed metrics. If an optimizer is available,
        it delegates to it for more advanced analysis; otherwise,
        it provides basic recommendations.

        Returns:
            Dict[str, Any]: A dictionary containing current metrics,
                        an urgency score, urgency level,
                        and a list of recommended actions to optimize the pool.
        """
        if hasattr(self.pool, "optimizer") and self.pool.optimizer:
            return self.pool.optimizer.force_optimization_analysis()

        # Basic recommendations if no optimizer is available.
        stats = self.pool.get_basic_stats()
        total_requests = stats["counters"].get("hits", 0) + stats["counters"].get("misses", 0)
        hit_rate = stats["counters"].get("hits", 0) / total_requests if total_requests > 0 else 0

        recommendations = []

        if hit_rate < 0.5 and total_requests > 50:
            recommendations.append(
                {
                    "type": "warning",
                    "parameter": "preset",
                    "current": self.current_preset.value,
                    "recommended": "HIGH_THROUGHPUT",
                    "reason": f"Low hit rate ({hit_rate:.1%}). Consider HIGH_THROUGHPUT preset.",
                    "impact": "high",
                }
            )

        if stats["counters"].get("corrupted", 0) > stats["counters"].get("creates", 0) * 0.1:
            recommendations.append(
                {
                    "type": "critical",
                    "parameter": "preset",
                    "current": self.current_preset.value,
                    "recommended": "DEVELOPMENT",
                    "reason": "High corrupted object rate. Use DEVELOPMENT for debugging.",
                    "impact": "high",
                }
            )

        return {
            "current_metrics": {"hit_rate": hit_rate},
            "urgency_score": len([r for r in recommendations if r["type"] == "critical"]) * 2,
            "urgency_level": (
                "critical" if any(r["type"] == "critical" for r in recommendations) else "info"
            ),
            "recommendations": recommendations,
            "note": (
                "Basic recommendations. Optimizer not available. "
                "Enable performance_metrics or optimizer for more details."
            ),
        }

    def get_health_status(self) -> Dict[str, Any]:
        """
        Provides a summary of the memory pool's health status.
        It assesses various metrics like hit rate, corruption rate, and validation failures
        to determine an overall health status (healthy, warning, critical)
        and lists any detected issues.

        Returns:
            Dict[str, Any]: A dictionary containing:
                        - 'status': The overall health status ('healthy', 'warning', 'critical').
                        - 'hit_rate': The current hit rate of the pool.
                        - 'corruption_rate': The rate of corrupted objects.
                        - 'total_requests': Total acquisition requests.
                        - 'total_pooled_objects': Number of objects currently in the pool.
                        - 'active_objects_count': Number of objects currently in use.
                        - 'issues': A list of identified health issues.
                        - 'uptime': Placeholder for pool uptime (currently 'unknown').
                        - 'preset': The name of the current configuration preset.
        """
        stats = self.pool.get_basic_stats()
        stats_counters = stats["counters"]

        # Calculate key health metrics.
        total_requests = stats_counters.get("hits", 0) + stats_counters.get("misses", 0)
        hit_rate = stats_counters.get("hits", 0) / total_requests if total_requests > 0 else 0
        corruption_rate = stats_counters.get("corrupted", 0) / max(
            1, stats_counters.get("creates", 0)
        )

        # Determine overall status based on issues.
        issues = []
        if hit_rate < 0.3 and total_requests > 20:
            issues.append(f"Very low hit rate ({hit_rate:.1%})")

        if corruption_rate > 0.1:
            issues.append(f"High corruption rate ({corruption_rate:.1%})")

        if stats_counters.get("validation_failures", 0) > stats_counters.get("hits", 0):
            issues.append("Frequent validation failures")

        # Set global status based on the severity and number of issues.
        if not issues:
            status = "healthy"
        elif len(issues) <= 1:
            status = "warning"
        else:
            status = "critical"

        return {
            "status": status,
            "hit_rate": hit_rate,
            "corruption_rate": corruption_rate,
            "total_requests": total_requests,
            "total_pooled_objects": stats.get("total_pooled_objects", 0),
            "active_objects_count": stats.get("active_objects_count", 0),
            "issues": issues,
            "uptime": "unknown",  # Placeholder for actual uptime tracking.
            "preset": self.current_preset.value,
        }

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """
        Generates a concise summary of the pool's status and key metrics, suitable for display
        in a monitoring dashboard. It includes health status, current preset, basic metrics,
        and optionally advanced performance metrics and alerts.

        Returns:
            Dict[str, Any]: A dictionary containing the dashboard summary.
        """
        health = self.get_health_status()
        stats = self.pool.get_basic_stats()

        dashboard = {
            "status": health["status"],
            "preset": self.current_preset.value,
            "metrics": {
                "hit_rate": health["hit_rate"],
                "total_pooled_objects": health["total_pooled_objects"],
                "active_objects_count": health["active_objects_count"],
                "total_creates": stats["counters"].get("creates", 0),
                "total_reuses": stats["counters"].get("reuses", 0),
            },
            "basic_stats": stats,
            "health_status": health,
        }

        # Add advanced metrics if available
        if self.pool.performance_metrics is not None:
            snapshot = self.pool.performance_metrics.create_snapshot()
            dashboard["advanced_metrics"] = {
                "avg_response_time_ms": snapshot.avg_acquisition_time_ms,
                "p95_response_time_ms": snapshot.p95_acquisition_time_ms,
                "throughput_ops_sec": snapshot.acquisitions_per_second,
                "lock_contention_rate": snapshot.lock_contention_rate,
            }

        # Add alerts
        if hasattr(self.pool, "optimizer") and self.pool.optimizer:
            analysis = self.pool.optimizer.force_optimization_analysis()
            dashboard["alerts"] = len(
                [r for r in analysis["recommendations"] if r["type"] == "critical"]
            )
            dashboard["warnings"] = len(
                [r for r in analysis["recommendations"] if r["type"] == "warning"]
            )
        else:
            dashboard["alerts"] = len(health["issues"])
            dashboard["warnings"] = 0

        return dashboard
