"""
Debugging and troubleshooting guide for the memory pool system.

This file demonstrates how to:
- Diagnose performance issues
- Identify memory leaks and unreleased objects
- Analyze statistics and metrics for debugging
- Resolve concurrency and contention issues
- Create custom diagnostic tools
- Monitor pool health in production
"""

import gc
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List

import psutil

from examples.factories import BytesIOFactory, PILImageFactory
from smartpool.config import MemoryConfig, MemoryPreset
from smartpool.core.smartpool_manager import SmartObjectManager

# === Diagnostic Tools ===


@dataclass
# pylint: disable=R0902
class DiagnosticReport:
    """Detailed diagnostic report."""

    timestamp: float
    pool_name: str
    issue_severity: str  # 'low', 'medium', 'high', 'critical'
    issues_found: List[str]
    recommendations: List[str]
    detailed_stats: Dict[str, Any]
    memory_usage: Dict[str, Any]
    thread_info: Dict[str, Any]


class PoolDiagnostic:
    """Diagnostic tool for memory pools."""

    def __init__(self, pool: SmartObjectManager, pool_name: str = "default"):
        self.pool = pool
        self.pool_name = pool_name
        self.monitoring_data = deque(maxlen=100)  # Keeps the last 100 measurements
        self._start_monitoring_time = time.time()

    def collect_basic_diagnostics(self) -> Dict[str, Any]:
        """Collects basic diagnostics."""

        stats = self.pool.get_basic_stats()
        health = self.pool.get_health_status()
        detailed_stats = self.pool.get_detailed_stats()

        # Performance metrics if available
        performance_data = {}
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            performance_data = {
                "hit_rate": snapshot.hit_rate,
                "avg_acquisition_time_ms": snapshot.avg_acquisition_time_ms,
                "p95_acquisition_time_ms": snapshot.p95_acquisition_time_ms,
                "p99_acquisition_time_ms": snapshot.p99_acquisition_time_ms,
                "lock_contention_rate": snapshot.lock_contention_rate,
                "acquisitions_per_second": snapshot.acquisitions_per_second,
                "peak_concurrent_acquisitions": snapshot.peak_concurrent_acquisitions,
            }

        return {
            "basic_stats": stats,
            "health": health,
            "detailed_stats": detailed_stats,
            "performance": performance_data,
            "config": {
                "max_objects_per_key": self.pool.default_config.max_objects_per_key,
                "ttl_seconds": self.pool.default_config.ttl_seconds,
                "cleanup_interval_seconds": self.pool.default_config.cleanup_interval_seconds,
            },
        }

    def analyze_memory_usage(self) -> Dict[str, Any]:
        """Analyzes memory usage."""

        process = psutil.Process()

        # Process memory
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()

        # Pool memory
        detailed_stats = self.pool.get_detailed_stats()
        pool_memory = detailed_stats.get("total_memory_bytes", 0)

        # Analysis by key
        memory_by_key = {}
        for key, key_stats in detailed_stats.get("by_key", {}).items():
            memory_by_key[key] = {
                "pooled_memory": key_stats.get("memory_bytes", 0),
                "pooled_count": key_stats.get("pooled_count", 0),
                "active_count": key_stats.get("active_count", 0),
            }

        return {
            "process_memory_mb": memory_info.rss / (1024 * 1024),
            "process_memory_percent": memory_percent,
            "pool_memory_mb": pool_memory / (1024 * 1024),
            "pool_memory_ratio": pool_memory / memory_info.rss if memory_info.rss > 0 else 0,
            "memory_by_key": memory_by_key,
            "gc_counts": gc.get_count(),
        }

    def detect_performance_issues(self) -> List[str]:
        """Detects performance issues."""

        issues = []

        # Check basic statistics
        stats = self.pool.get_basic_stats()
        total_requests = stats.get("hits", 0) + stats.get("misses", 0)

        if total_requests > 0:
            hit_rate = stats.get("hits", 0) / total_requests

            if hit_rate < 0.3:
                issues.append(f"Very low hit rate: {hit_rate:.1%}")
            elif hit_rate < 0.6:
                issues.append(f"Suboptimal hit rate: {hit_rate:.1%}")

        # Check for corrupted objects
        corrupted = stats.get("corrupted", 0)
        if corrupted > 0:
            issues.append(f"Corrupted objects detected: {corrupted}")

        # Check for validation failures
        validation_failures = stats.get("validation_failures", 0)
        if validation_failures > stats.get("hits", 0) * 0.1:
            issues.append(f"High validation failure rate: {validation_failures}")

        # Advanced performance metrics
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()

            if snapshot.avg_acquisition_time_ms > 20.0:
                issues.append(
                    f"High average acquisition time: {snapshot.avg_acquisition_time_ms:.1f}ms"
                )

            if snapshot.p95_acquisition_time_ms > 100.0:
                issues.append(
                    f"Very high P95 acquisition time: {snapshot.p95_acquisition_time_ms:.1f}ms"
                )

            if snapshot.lock_contention_rate > 0.3:
                issues.append(f"High lock contention: {snapshot.lock_contention_rate:.1%}")

        # Check memory usage
        memory_analysis = self.analyze_memory_usage()
        if memory_analysis["pool_memory_ratio"] > 0.5:
            issues.append(
                "Pool uses high percentage of process memory:"
                f" {memory_analysis['pool_memory_ratio']:.1%}"
            )

        return issues

    def detect_memory_leaks(self) -> List[str]:
        """Detects potential memory leaks."""

        issues = []

        # Check active vs. pooled objects
        stats = self.pool.get_basic_stats()
        active_objects_count = stats.get("active_objects_count", 0)
        total_pooled_objects = stats.get("total_pooled_objects", 0)

        if active_objects_count > total_pooled_objects * 2:
            issues.append(
                f"Many more active objects ({active_objects_count})"
                f" than pooled ({total_pooled_objects})"
            )

        # Check for dead weak references
        if hasattr(self.pool, "active_manager"):
            active_stats = self.pool.active_manager.get_basic_stats()
            dead_refs = active_stats.get("dead_weakrefs", 0)

            if dead_refs > 10:
                issues.append(f"Many dead weak references: {dead_refs}")

        # Compare with previous measurements
        current_memory = self.analyze_memory_usage()
        self.monitoring_data.append(
            {
                "timestamp": time.time(),
                "process_memory": current_memory["process_memory_mb"],
                "pool_memory": current_memory["pool_memory_mb"],
                "active_objects_count": active_objects_count,
            }
        )

        if len(self.monitoring_data) >= 10:
            # Analyze the trend
            recent_data = list(self.monitoring_data)[-10:]
            memory_growth = recent_data[-1]["process_memory"] - recent_data[0]["process_memory"]

            if memory_growth > 50:  # More than 50MB growth
                issues.append(f"Significant memory growth detected: +{memory_growth:.1f}MB")

        return issues

    def detect_concurrency_issues(self) -> List[str]:
        """Detects concurrency issues."""

        issues = []

        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()

            # Lock contention
            if snapshot.lock_contention_rate > 0.2:
                issues.append(f"Lock contention detected: {snapshot.lock_contention_rate:.1%}")

            # Peak concurrency vs. configuration
            max_expected_concurrency = self.pool.default_config.max_expected_concurrency
            if snapshot.peak_concurrent_acquisitions > max_expected_concurrency * 1.5:
                issues.append(
                    f"Peak concurrency ({snapshot.peak_concurrent_acquisitions}) "
                    f"exceeds expected ({max_expected_concurrency})"
                )

        # Check active thread count
        thread_count = threading.active_count()
        if thread_count > 50:
            issues.append(f"High thread count: {thread_count}")

        return issues

    def generate_comprehensive_report(self) -> DiagnosticReport:
        """Generates a comprehensive diagnostic report."""

        # Collect all data
        basic_diagnostics = self.collect_basic_diagnostics()
        memory_analysis = self.analyze_memory_usage()

        # Detect issues
        performance_issues = self.detect_performance_issues()
        memory_issues = self.detect_memory_leaks()
        concurrency_issues = self.detect_concurrency_issues()

        all_issues = performance_issues + memory_issues + concurrency_issues

        # Determine severity
        severity = "low"
        if any("critical" in issue.lower() or "high" in issue.lower() for issue in all_issues):
            severity = "high"
        elif any("very" in issue.lower() or "significant" in issue.lower() for issue in all_issues):
            severity = "medium"
        elif all_issues:
            severity = "medium"

        # Generate recommendations
        recommendations = self._generate_recommendations(all_issues, basic_diagnostics)

        return DiagnosticReport(
            timestamp=time.time(),
            pool_name=self.pool_name,
            issue_severity=severity,
            issues_found=all_issues,
            recommendations=recommendations,
            detailed_stats=basic_diagnostics,
            memory_usage=memory_analysis,
            thread_info={"active_threads": threading.active_count()},
        )

    # pylint: disable=W0613
    def _generate_recommendations(
        self, issues: List[str], diagnostics: Dict[str, Any]
    ) -> List[str]:
        """Generates recommendations based on detected issues."""

        recommendations = []

        # Recommendations for hit rate
        if any("hit rate" in issue for issue in issues):
            recommendations.append("Increase pool max_objects_per_key or TTL to improve hit rate")
            recommendations.append("Consider using HIGH_THROUGHPUT preset")

        # Recommendations for acquisition times
        if any("acquisition time" in issue for issue in issues):
            recommendations.append("Reduce max_validation_attempts for faster acquisitions")
            recommendations.append("Enable auto-tuning to optimize pool configuration")

        # Recommendations for contention
        if any("contention" in issue for issue in issues):
            recommendations.append("Increase cleanup_interval_seconds to reduce lock contention")
            recommendations.append("Consider splitting into multiple specialized pools")

        # Recommendations for memory
        if any("memory" in issue for issue in issues):
            recommendations.append("Enable background cleanup to free unused objects")
            recommendations.append("Reduce TTL to expire objects sooner")
            recommendations.append("Consider LOW_MEMORY preset")

        # General recommendations
        if not recommendations:
            recommendations.append("Pool appears healthy - continue monitoring")

        return recommendations


# === Real-time Monitoring Tools ===


class RealTimeMonitor:
    """Real-time monitor for the pool."""

    def __init__(self, pool: SmartObjectManager, interval: float = 1.0):
        self.pool = pool
        self.interval = interval
        self.diagnostic = PoolDiagnostic(pool)
        self.running = False
        self.thread = None
        self.alerts = deque(maxlen=50)

    def start(self):
        """Starts monitoring."""
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print(f"Real-time monitoring started (interval: {self.interval}s)")

    def stop(self):
        """Stops monitoring."""
        self.running = False
        if self.thread:
            self.thread.join()
        print("Real-time monitoring stopped")

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                # Collect metrics
                stats = self.pool.get_basic_stats()

                # Real-time checks
                current_time = time.time()

                # Alert on high active objects
                active_objects_count = stats.get("active_objects_count", 0)
                if active_objects_count > 50:
                    self.alerts.append(
                        {
                            "timestamp": current_time,
                            "type": "high_active_objects_count",
                            "message": f"High active objects: {active_objects_count}",
                            "severity": "medium",
                        }
                    )

                # Alert on performance metrics
                if self.pool.performance_metrics:
                    snapshot = self.pool.performance_metrics.create_snapshot()

                    if snapshot.avg_acquisition_time_ms > 50.0:
                        self.alerts.append(
                            {
                                "timestamp": current_time,
                                "type": "slow_acquisitions",
                                "message": (
                                    f"Slow acquisitions: "
                                    f"{snapshot.avg_acquisition_time_ms:.1f}ms avg"
                                ),
                                "severity": "high",
                            }
                        )

                time.sleep(self.interval)

            except Exception as e:  # pylint: disable=W0718
                print(f"Monitoring error: {e}")
                time.sleep(self.interval)

    def get_recent_alerts(self, max_age_seconds: float = 300.0) -> List[Dict[str, Any]]:
        """Retrieves recent alerts."""
        current_time = time.time()
        return [
            alert for alert in self.alerts if current_time - alert["timestamp"] <= max_age_seconds
        ]


# === Test Scenarios and Issue Reproduction ===


def simulate_memory_leak():
    """Simulates a memory leak to test detection."""

    print("=== Memory Leak Simulation ===\n")

    factory = BytesIOFactory()
    pool = SmartObjectManager(factory, preset=MemoryPreset.DEVELOPMENT)
    diagnostic = PoolDiagnostic(pool, "leak_test")

    # Simulate unreleased objects
    leaked_objects = []

    try:
        print("Phase 1: Normal usage")

        for i in range(10):
            with pool.acquire_context(1024) as buffer:
                buffer.write(f"Normal data {i}".encode())

        report1 = diagnostic.generate_comprehensive_report()
        print(f"Issues detected: {len(report1.issues_found)}")

        print("\nPhase 2: Leak simulation (unreleased objects)")

        # Acquire objects without releasing them
        for i in range(20):
            obj_id, key, obj = pool.acquire(1024)
            leaked_objects.append((obj_id, key, obj))
            obj.write(f"Leaked data {i}".encode())

        time.sleep(0.1)  # Allow time for metrics to update

        report2 = diagnostic.generate_comprehensive_report()
        print(f"Issues detected after leak: {len(report2.issues_found)}")

        for issue in report2.issues_found:
            print(f"  - {issue}")

        print("\nRecommendations:")
        for rec in report2.recommendations[:3]:
            print(f"  - {rec}")

        # Analyze memory
        memory_analysis = diagnostic.analyze_memory_usage()
        print("\nMemory usage:")
        print(f"  Process: {memory_analysis['process_memory_mb']:.1f} MB")
        print(f"  Pool: {memory_analysis['pool_memory_mb']:.1f} MB")
        print(f"  Ratio: {memory_analysis['pool_memory_ratio']:.1%}")

    finally:
        # Clean up the "leaked" objects
        for obj_id, key, obj in leaked_objects:
            pool.release(obj_id, key, obj)

        pool.shutdown()


def simulate_high_contention():
    """Simulates high contention to test detection."""

    print("\n=== High Contention Simulation ===\n")

    factory = BytesIOFactory()
    config = MemoryConfig(
        max_objects_per_key=5,  # Small pool to force contention
        enable_performance_metrics=True,
        enable_acquisition_tracking=True,
    )
    pool = SmartObjectManager(factory, default_config=config)
    diagnostic = PoolDiagnostic(pool, "contention_test")

    def worker_function(worker_id: int, operations: int):
        """Worker function that will create contention."""
        for i in range(operations):
            try:
                with pool.acquire_context(1024) as buffer:
                    buffer.write(f"Worker {worker_id} op {i}".encode())
                    time.sleep(0.001)  # Simulate work
            except Exception as e:  # pylint: disable=W0718
                print(f"Worker {worker_id} error: {e}")

    try:
        print("Launching concurrent workers...")

        # Launch multiple workers in parallel to create contention
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for worker_id in range(10):
                future = executor.submit(worker_function, worker_id, 20)
                futures.append(future)

            # Wait for completion
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:  # pylint: disable=W0718
                    print(f"Worker failed: {e}")

        # Analyze the results
        report = diagnostic.generate_comprehensive_report()

        print("\n--- Contention Report ---")
        print(f"Severity: {report.issue_severity}")
        print(f"Issues detected: {len(report.issues_found)}")

        for issue in report.issues_found:
            print(f"  - {issue}")

        # Performance metrics
        if "performance" in report.detailed_stats:
            perf = report.detailed_stats["performance"]
            if perf:
                print("\nPerformance metrics:")
                print(f"  Hit rate: {perf.get('hit_rate', 0):.1%}")
                print(f"  Average time: {perf.get('avg_acquisition_time_ms', 0):.1f}ms")
                print(f"  Contention: {perf.get('lock_contention_rate', 0):.1%}")

    finally:
        pool.shutdown()


def simulate_performance_degradation():
    """Simulates performance degradation."""

    print("\n=== Performance Degradation Simulation ===\n")

    factory = PILImageFactory()  # Heavier factory
    config = MemoryConfig(
        max_objects_per_key=3,  # Very small pool
        ttl_seconds=10.0,  # Short TTL
        enable_performance_metrics=True,
    )
    pool = SmartObjectManager(factory, default_config=config)
    diagnostic = PoolDiagnostic(pool, "performance_test")

    try:
        print("Phase 1: Light load")

        start_time = time.time()
        for i in range(10):
            with pool.acquire_context(100, 100, "RGB"):
                pass  # Just acquire and release

        light_time = time.time() - start_time

        print("Phase 2: Heavy load (large images)")

        start_time = time.time()
        for i in range(20):
            # Different large images to force misses
            size = 500 + (i % 5) * 100
            with pool.acquire_context(size, size, "RGB"):
                pass

        heavy_time = time.time() - start_time

        print(f"Light load time: {light_time * 1000:.1f}ms")
        print(f"Heavy load time: {heavy_time * 1000:.1f}ms")
        print(f"Degradation: {(heavy_time / light_time):.1f}x")

        # Diagnosis after heavy load
        report = diagnostic.generate_comprehensive_report()

        print("\n--- Performance Diagnosis ---")
        for issue in report.issues_found:
            print(f"  Issue: {issue}")

        for rec in report.recommendations:
            print(f"  Rec: {rec}")

    finally:
        pool.shutdown()


def debug_stuck_objects():
    """Debug stuck/unreleased objects."""

    print("\n=== Debugging Stuck Objects ===\n")

    factory = BytesIOFactory()
    pool = SmartObjectManager(factory, preset=MemoryPreset.DEVELOPMENT)

    try:
        # Create objects with different usage patterns
        print("Creating objects with various patterns...")

        # Normal pattern
        with pool.acquire_context(1024) as buffer:
            buffer.write(b"Normal usage")

        # Pattern with exception (should still release)
        try:
            with pool.acquire_context(1024) as buffer:
                buffer.write(b"Usage with exception")
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Manual acquisition (potentially problematic)
        obj_id, key, obj = pool.acquire(1024)
        obj.write(b"Manual acquisition")

        # State before release
        stats_before = pool.get_basic_stats()
        _ = pool.get_detailed_stats()

        print("Before release:")
        print(f"  Active objects: {stats_before.get('active_objects_count', 0)}")
        print(f"  Pooled objects: {stats_before.get('total_pooled_objects', 0)}")

        # Analyze active objects
        if hasattr(pool, "active_manager"):
            active_info = pool.active_manager.get_active_objects_count_info()
            print(f"  Active object details: {len(active_info)}")

            for obj_id_active, info in active_info.items():
                age = time.time() - info.created_at
                print(
                    f"    ID {obj_id_active}: {info.key}, age {age:.1f}s, "
                    f"accesses {info.access_count}"
                )

        # Release the manual object
        pool.release(obj_id, key, obj)

        # State after release
        stats_after = pool.get_basic_stats()
        print("\nAfter release:")
        print(f"  Active objects: {stats_after.get('active_objects_count', 0)}")
        print(f"  Pooled objects: {stats_after.get('total_pooled_objects', 0)}")

        # Force a cleanup to see the effect
        cleaned = pool.force_cleanup()
        print(f"Forced cleanup: {cleaned} objects cleaned")

    finally:
        pool.shutdown()


def comprehensive_debugging_session():
    """Comprehensive debugging session."""

    print("\n=== Comprehensive Debugging Session ===\n")

    factory = BytesIOFactory()
    pool = SmartObjectManager(factory, preset=MemoryPreset.DEVELOPMENT)
    diagnostic = PoolDiagnostic(pool, "debug_session")
    monitor = RealTimeMonitor(pool, interval=0.5)

    try:
        # Start monitoring
        monitor.start()

        print("1. Baseline - initial state")
        baseline_report = diagnostic.generate_comprehensive_report()
        print(f"   Issues: {len(baseline_report.issues_found)}")

        print("\n2. Normal load")
        for i in range(30):
            with pool.acquire_context(1024) as buffer:
                buffer.write(f"Normal load {i}".encode())

        print("\n3. Load with simulated problems")

        # Create contention
        def contention_worker():
            for i in range(10):
                with pool.acquire_context(2048) as buffer:
                    buffer.write(f"Contention data {i}".encode())
                    time.sleep(0.01)

        threads = []
        for _ in range(5):
            thread = threading.Thread(target=contention_worker)
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        print("\n4. Final analysis")
        final_report = diagnostic.generate_comprehensive_report()

        print("--- Final Report ---")
        print(f"Severity: {final_report.issue_severity}")
        print(f"Issues: {len(final_report.issues_found)}")

        for issue in final_report.issues_found:
            print(f"  - {issue}")

        print("\nMain recommendations:")
        for rec in final_report.recommendations[:3]:
            print(f"  - {rec}")

        # Real-time monitoring alerts
        alerts = monitor.get_recent_alerts()
        if alerts:
            print(f"\nReal-time alerts ({len(alerts)}):")
            for alert in alerts[-5:]:  # Last 5
                print(f"  {alert['type']}: {alert['message']}")

    finally:
        monitor.stop()
        pool.shutdown()


if __name__ == "__main__":
    print("=== Debugging and Troubleshooting Guide ===")
    print("This module demonstrates various tools and techniques for diagnosing")
    print("performance and memory issues in pools.")
    print()

    simulate_memory_leak()
    simulate_high_contention()
    simulate_performance_degradation()
    debug_stuck_objects()
    comprehensive_debugging_session()

    print("\n=== Available Debugging Tools ===")
    print("1. PoolDiagnostic - Comprehensive and automated diagnostics")
    print("2. RealTimeMonitor - Real-time monitoring with alerts")
    print("3. DiagnosticReport - Structured reports for analysis")
    print("4. Automatic detection of:")
    print("   - Memory leaks")
    print("   - Performance issues")
    print("   - Lock contention")
    print("   - Corrupted objects")
    print("   - Suboptimal configuration")
    print()
    print("=== Key Metrics to Monitor ===")
    print("- Hit rate (>60% recommended)")
    print("- Average acquisition time (<20ms recommended)")
    print("- Contention rate (<20% recommended)")
    print("- Active/pooled object ratio")
    print("- Pool memory usage")
    print("- Number of corrupted objects (0 is ideal)")
