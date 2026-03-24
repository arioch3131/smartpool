# Troubleshooting & Diagnostic Guide

## Overview

This comprehensive guide provides systematic approaches for diagnosing and resolving issues with the Adaptive Memory Pool system. It covers common problems, diagnostic tools, step-by-step troubleshooting methodologies, and preventive measures for production environments.

## Common Problems and Symptoms

### Performance Issues

#### Low Hit Rate
**Symptoms:**
- High object creation frequency
- Poor application performance
- Increased memory allocations

**Diagnostic Commands:**
```python
# Check current hit rate
total_requests = stats['counters'].get('hits', 0) + stats['counters'].get('misses', 0)
hit_rate = stats['counters'].get('hits', 0) / max(1, total_requests)
print(f"Hit rate: {hit_rate:.2%}")

# Detailed analysis
health = pool.get_health_status()
if health['hit_rate'] < 0.6:
    print(f"⚠️  Low hit rate detected: {health['hit_rate']:.2%}")
```

**Root Causes:**
1. **Pool too small**: Not enough objects to satisfy concurrent requests
2. **TTL too short**: Objects expire before reuse
3. **Over-granular keys**: Factory `get_key()` creates too many unique keys
4. **Validation failures**: Objects fail validation and get destroyed

#### High Acquisition Latency
**Symptoms:**
- Slow response times
- High average acquisition times
- Thread blocking

**Diagnostic Commands:**
```python
# Check acquisition times
if pool.performance_metrics:
    snapshot = pool.performance_metrics.create_snapshot()
    print(f"Average acquisition time: {snapshot.avg_acquisition_time_ms:.2f}ms")
    print(f"95th percentile time: {snapshot.p95_acquisition_time_ms:.2f}ms")
    
    if snapshot.avg_acquisition_time_ms > 20.0:
        print("⚠️  High latency detected")
```

**Root Causes:**
1. **Excessive validation**: Too many validation attempts
2. **Slow factory methods**: `create()`, `reset()`, or `validate()` are expensive
3. **Lock contention**: Multiple threads competing for pool access
4. **Full pool**: No available objects, forcing creation

#### Lock Contention
**Symptoms:**
- Threads waiting for pool access
- High lock contention rates
- Degraded concurrent performance

**Diagnostic Commands:**
```python
# Check lock contention
if pool.performance_metrics:
    snapshot = pool.performance_metrics.create_snapshot()
    contention_rate = snapshot.lock_contention_rate
    print(f"Lock contention rate: {contention_rate:.2%}")
    
    if contention_rate > 0.3:
        print("⚠️  High lock contention detected")
```

### Memory Issues

#### Memory Leaks
**Symptoms:**
- Continuously growing memory usage
- Pool size increasing over time
- Out-of-memory errors

**Diagnostic Commands:**
```python
import psutil
import time

def monitor_memory_growth():
    """Monitor pool memory usage over time."""
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    initial_objects = pool.get_basic_stats().get('total_pooled_objects', 0)
    
    time.sleep(300)  # Wait 5 minutes
    
    final_memory = process.memory_info().rss
    final_objects = pool.get_basic_stats().get('total_pooled_objects', 0)
    
    memory_growth = (final_memory - initial_memory) / 1024 / 1024  # MB
    object_growth = final_objects - initial_objects
    
    print(f"Memory growth: {memory_growth:.1f} MB")
    print(f"Object growth: {object_growth}")
    
    if memory_growth > 50 and object_growth > 10:
        print("⚠️  Possible memory leak detected")

monitor_memory_growth()
```

#### Object Corruption
**Symptoms:**
- Validation failures
- Corrupted object warnings
- Unexpected application errors

**Diagnostic Commands:**
```python
# Check corruption statistics
stats = pool.get_basic_stats()
corrupted_count = stats['counters'].get('corrupted', 0)
validation_failures = stats['counters'].get('validation_failures', 0)

print(f"Corrupted objects: {corrupted_count}")
print(f"Validation failures: {validation_failures}")

if corrupted_count > 0:
    print("⚠️  Object corruption detected")
```

## Built-in Diagnostic Tools

### PoolDiagnostic System

The system includes comprehensive diagnostic tools for automated problem detection:

```python
from collections import deque
from dataclasses import dataclass
from typing import Dict, Any, List
import time

@dataclass
class DiagnosticReport:
    """Comprehensive diagnostic report."""
    timestamp: float
    pool_name: str
    issue_severity: str  # 'low', 'medium', 'high', 'critical'
    issues_found: List[str]
    recommendations: List[str]
    detailed_stats: Dict[str, Any]
    memory_usage: Dict[str, Any]
    thread_info: Dict[str, Any]

class PoolDiagnostic:
    """Advanced diagnostic tool for memory pools."""
    
    def __init__(self, pool, pool_name="default"):
        self.pool = pool
        self.pool_name = pool_name
        self.monitoring_data = deque(maxlen=100)
        self._start_time = time.time()
    
    def collect_basic_diagnostics(self) -> Dict[str, Any]:
        """Collect comprehensive pool diagnostics."""
        stats = self.pool.get_basic_stats()
        health = self.pool.get_health_status()
        
        diagnostics = {
            'uptime': time.time() - self._start_time,
            'total_requests': stats['counters'].get('hits', 0) + stats['counters'].get('misses', 0),
            'hit_rate': health['hit_rate'],
            'corruption_rate': health['corruption_rate'],
            'active_objects_count': health['active_objects_count'],
            'total_pooled_objects': health['total_pooled_objects'],
            'memory_mb': self._estimate_memory_usage()
        }
        
        # Add performance metrics if available
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            diagnostics.update({
                'avg_acquisition_time_ms': snapshot.avg_acquisition_time_ms,
                'p95_acquisition_time_ms': snapshot.p95_acquisition_time_ms,
                'lock_contention_rate': snapshot.lock_contention_rate,
                'throughput_ops_sec': snapshot.acquisitions_per_second
            })
        
        return diagnostics
    
    def detect_performance_issues(self) -> List[str]:
        """Detect performance-related issues."""
        issues = []
        stats = self.pool.get_basic_stats()
        
        # Check hit rate
        total_requests = stats['counters'].get('hits', 0) + stats['counters'].get('misses', 0)
        if total_requests > 0:
            hit_rate = stats['counters'].get('hits', 0) / total_requests
            if hit_rate < 0.3:
                issues.append(f"Critical: Very low hit rate ({hit_rate:.1%})")
            elif hit_rate < 0.6:
                issues.append(f"Warning: Suboptimal hit rate ({hit_rate:.1%})")
        
        # Check performance metrics
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            
            if snapshot.avg_acquisition_time_ms > 50:
                issues.append(f"Critical: High avg acquisition time ({snapshot.avg_acquisition_time_ms:.1f}ms)")
            elif snapshot.avg_acquisition_time_ms > 20:
                issues.append(f"Warning: Elevated avg acquisition time ({snapshot.avg_acquisition_time_ms:.1f}ms)")
            
            if snapshot.lock_contention_rate > 0.4:
                issues.append(f"Critical: Very high lock contention ({snapshot.lock_contention_rate:.1%})")
            elif snapshot.lock_contention_rate > 0.2:
                issues.append(f"Warning: High lock contention ({snapshot.lock_contention_rate:.1%})")
        
        return issues
    
    def detect_memory_issues(self) -> List[str]:
        """Detect memory-related issues."""
        issues = []
        
        # Check for memory leaks
        if len(self.monitoring_data) > 10:
            recent_memory = [d['memory_mb'] for d in list(self.monitoring_data)[-10:]]
            growth_rate = (recent_memory[-1] - recent_memory[0]) / len(recent_memory)
            
            if growth_rate > 5:  # > 5MB per sample
                issues.append(f"Critical: Possible memory leak (growth: {growth_rate:.1f}MB/sample)")
            elif growth_rate > 1:
                issues.append(f"Warning: Memory growth detected ({growth_rate:.1f}MB/sample)")
        
        # Check corruption rate
        health = self.pool.get_health_status()
        if health['corruption_rate'] > 0.1:
            issues.append(f"Critical: High corruption rate ({health['corruption_rate']:.1%})")
        elif health['corruption_rate'] > 0.02:
            issues.append(f"Warning: Elevated corruption rate ({health['corruption_rate']:.1%})")
        
        return issues
    
    def generate_comprehensive_report(self) -> DiagnosticReport:
        """Generate complete diagnostic report."""
        diagnostics = self.collect_basic_diagnostics()
        performance_issues = self.detect_performance_issues()
        memory_issues = self.detect_memory_issues()
        
        all_issues = performance_issues + memory_issues
        
        # Determine overall severity
        severity = "low"
        if any("Critical" in issue for issue in all_issues):
            severity = "critical"
        elif any("Warning" in issue for issue in all_issues):
            severity = "medium"
        elif all_issues:
            severity = "low"
        
        # Generate recommendations
        recommendations = self._generate_recommendations(all_issues, diagnostics)
        
        return DiagnosticReport(
            timestamp=time.time(),
            pool_name=self.pool_name,
            issue_severity=severity,
            issues_found=all_issues,
            recommendations=recommendations,
            detailed_stats=diagnostics,
            memory_usage=self._analyze_memory_usage(),
            thread_info={'active_threads': self._count_active_threads()}
        )
    
    def _generate_recommendations(self, issues: List[str], diagnostics: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on issues."""
        recommendations = []
        
        # Hit rate recommendations
        if any("hit rate" in issue.lower() for issue in issues):
            if diagnostics['hit_rate'] < 0.5:
                recommendations.append("Increase pool max_objects_per_key to improve object reuse")
                recommendations.append("Consider extending TTL to keep objects longer")
            recommendations.append("Review factory get_key() for over-granular keys")
        
        # Latency recommendations
        if any("acquisition time" in issue.lower() for issue in issues):
            recommendations.append("Reduce max_validation_attempts to speed up acquisition")
            recommendations.append("Profile factory methods (create, reset, validate) for performance")
            recommendations.append("Consider increasing pool size to reduce creation overhead")
        
        # Lock contention recommendations
        if any("contention" in issue.lower() for issue in issues):
            recommendations.append("Increase cleanup_interval_seconds to reduce background lock usage")
            recommendations.append("Optimize factory methods to minimize time in locks")
            recommendations.append("Consider using multiple pool instances for different object types")
        
        # Memory recommendations
        if any("memory" in issue.lower() or "leak" in issue.lower() for issue in issues):
            recommendations.append("Review factory reset() method for incomplete cleanup")
            recommendations.append("Implement proper destroy() method for resource cleanup")
            recommendations.append("Check for circular references in managed objects")
            recommendations.append("Reduce TTL to force more frequent object disposal")
        
        # Corruption recommendations
        if any("corruption" in issue.lower() for issue in issues):
            recommendations.append("Review factory validate() method implementation")
            recommendations.append("Check for thread safety issues in factory methods")
            recommendations.append("Increase max_validation_attempts for transient failures")
        
        return recommendations
    
    def _estimate_memory_usage(self) -> float:
        """Estimate pool memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def _analyze_memory_usage(self) -> Dict[str, Any]:
        """Analyze detailed memory usage."""
        stats = self.pool.get_basic_stats()
        
        return {
            'process_memory_mb': self._estimate_memory_usage(),
            'total_pooled_objects': stats.get('total_pooled_objects', 0),
            'active_objects_count': stats.get('active_objects_count', 0),
            'estimated_pool_memory_mb': stats.get('total_pooled_objects', 0) * 0.1  # Rough estimate
        }
    
    def _count_active_threads(self) -> int:
        """Count active threads."""
        import threading
        return threading.active_count()

# Usage example
diagnostic = PoolDiagnostic(pool, "production_pool")
report = diagnostic.generate_comprehensive_report()

print(f"=== Diagnostic Report ===")
print(f"Pool: {report.pool_name}")
print(f"Severity: {report.issue_severity}")
print(f"Issues found: {len(report.issues_found)}")

for issue in report.issues_found:
    print(f"  🔍 {issue}")

print(f"\nRecommendations:")
for rec in report.recommendations:
    print(f"  💡 {rec}")
```

### Real-Time Monitoring

Set up continuous monitoring with automatic issue detection:

```python
import threading
from collections import deque

class RealTimeMonitor:
    """Real-time pool monitoring with alerting."""
    
    def __init__(self, pool, interval=30.0):
        self.pool = pool
        self.interval = interval
        self.running = False
        self.thread = None
        self.alerts = deque(maxlen=50)
        
        # Alert thresholds
        self.thresholds = {
            'hit_rate_low': 0.4,
            'response_time_high': 50.0,
            'lock_contention_high': 0.3,
            'memory_growth_high': 10.0  # MB per interval
        }
        
        self.previous_memory = 0.0
    
    def start(self):
        """Start real-time monitoring."""
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print("Real-time monitoring started")
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        if self.thread:
            self.thread.join()
        print("Real-time monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._check_alerts()
                time.sleep(self.interval)
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(self.interval)
    
    def _check_alerts(self):
        """Check for alert conditions."""
        health = self.pool.get_health_status()
        
        # Check hit rate
        if health['hit_rate'] < self.thresholds['hit_rate_low']:
            self._add_alert('low_hit_rate', 
                          f"Hit rate {health['hit_rate']:.1%} below threshold",
                          'medium')
        
        # Check performance metrics
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            
            if snapshot.avg_acquisition_time_ms > self.thresholds['response_time_high']:
                severity = 'critical' if snapshot.avg_acquisition_time_ms > 100 else 'high'
                self._add_alert('high_response_time',
                              f"Response time {snapshot.avg_acquisition_time_ms:.1f}ms too high",
                              severity)
            
            if snapshot.lock_contention_rate > self.thresholds['lock_contention_high']:
                self._add_alert('high_lock_contention',
                              f"Lock contention {snapshot.lock_contention_rate:.1%} too high",
                              'high')
        
        # Check memory growth
        current_memory = self._get_memory_usage()
        if self.previous_memory > 0:
            growth = current_memory - self.previous_memory
            if growth > self.thresholds['memory_growth_high']:
                self._add_alert('memory_growth',
                              f"Memory grew by {growth:.1f}MB in {self.interval}s",
                              'high')
        self.previous_memory = current_memory
    
    def _add_alert(self, alert_type: str, message: str, severity: str):
        """Add new alert."""
        alert = {
            'timestamp': time.time(),
            'type': alert_type,
            'message': message,
            'severity': severity
        }
        self.alerts.append(alert)
        
        # Print alert immediately
        severity_symbol = {'low': '📘', 'medium': '⚠️', 'high': '🔴', 'critical': '🚨'}
        print(f"{severity_symbol.get(severity, '❓')} [{severity.upper()}] {message}")
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil
            return psutil.Process().memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def get_recent_alerts(self, minutes=60) -> List[Dict]:
        """Get recent alerts within specified time window."""
        cutoff = time.time() - (minutes * 60)
        return [alert for alert in self.alerts if alert['timestamp'] > cutoff]

# Usage
monitor = RealTimeMonitor(pool, interval=60.0)  # Check every minute
monitor.start()

# Later, get recent alerts
recent_alerts = monitor.get_recent_alerts(30)  # Last 30 minutes
print(f"Alerts in last 30 minutes: {len(recent_alerts)}")
```

## Systematic Troubleshooting Methodologies

### Step-by-Step Diagnosis Process

#### 1. Initial Assessment
```python
def quick_health_check(pool):
    """Perform quick health assessment."""
    print("=== Quick Health Check ===")
    
    # Basic health
    health = pool.get_health_status()
    print(f"Status: {health['status']}")
    print(f"Hit Rate: {health['hit_rate']:.2%}")
    print(f"Active Objects: {health['active_objects_count']}")
    print(f"Pooled Objects: {health['total_pooled_objects']}")
    
    # Immediate red flags
    red_flags = []
    if health['status'] == 'critical':
        red_flags.append("Pool in critical state")
    if health['hit_rate'] < 0.3:
        red_flags.append(f"Very low hit rate: {health['hit_rate']:.2%}")
    if len(health['issues']) > 3:
        red_flags.append(f"Multiple issues detected: {len(health['issues'])}")
    
    if red_flags:
        print("\n🚨 Immediate Issues:")
        for flag in red_flags:
            print(f"  - {flag}")
        return False
    
    print("✅ No immediate critical issues")
    return True

# Run quick check
if not quick_health_check(pool):
    print("⚠️  Requires immediate attention")
```

#### 2. Detailed Performance Analysis
```python
def detailed_performance_analysis(pool):
    """Comprehensive performance analysis."""
    print("\n=== Performance Analysis ===")
    
    # Get comprehensive metrics
    if pool.performance_metrics:
        report = pool.performance_metrics.get_performance_report()
        current = report['current_metrics']
        
        print(f"Total Acquisitions: {current['total_acquisitions']}")
        print(f"Hit Rate: {current['hit_rate']:.2%}")
        print(f"Avg Time: {current['avg_acquisition_time_ms']:.2f}ms")
        print(f"P95 Time: {current['p95_acquisition_time_ms']:.2f}ms")
        print(f"Throughput: {current.get('acquisitions_per_second', 0):.1f} ops/sec")
        
        # Performance issues
        if current['hit_rate'] < 0.6:
            print(f"⚠️  Hit rate below optimal (target: >60%)")
        
        if current['avg_acquisition_time_ms'] > 20:
            print(f"⚠️  High average latency (target: <20ms)")
        
        if current.get('lock_contention_rate', 0) > 0.2:
            print(f"⚠️  High lock contention (target: <20%)")
        
        # Trend analysis
        trends = report['trends']
        if len(trends['hit_rate_trend']) > 1:
            hit_trend = trends['hit_rate_trend'][-1] - trends['hit_rate_trend'][0]
            direction = "↑" if hit_trend > 0 else "↓"
            print(f"Hit Rate Trend: {direction} {abs(hit_trend):.2%}")
    else:
        print("⚠️  Performance metrics not enabled - limited analysis")

detailed_performance_analysis(pool)
```

#### 3. Memory and Resource Analysis
```python
def memory_resource_analysis(pool):
    """Analyze memory usage and resource consumption."""
    print("\n=== Memory & Resource Analysis ===")
    
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        
        print(f"Process Memory: {memory_info.rss / 1024 / 1024:.1f} MB")
        print(f"Virtual Memory: {memory_info.vms / 1024 / 1024:.1f} MB")
        
        # Pool-specific memory
        stats = pool.get_basic_stats()
        total_pooled_objects = stats.get('total_pooled_objects', 0)
        active_objects_count = stats.get('active_objects_count', 0)
        
        print(f"Pooled Objects: {total_pooled_objects}")
        print(f"Active Objects: {active_objects_count}")
        print(f"Total Objects: {total_pooled_objects + active_objects_count}")
        
        # Memory efficiency
        if total_pooled_objects > 0:
            efficiency = active_objects_count / (total_pooled_objects + active_objects_count)
            print(f"Object Utilization: {efficiency:.2%}")
            
            if efficiency < 0.2:
                print("⚠️  Low object utilization - consider reducing pool size")
        
        # Check for memory growth
        if hasattr(pool, '_previous_memory'):
            growth = memory_info.rss - pool._previous_memory
            if growth > 10 * 1024 * 1024:  # 10MB
                print(f"⚠️  Memory growth detected: {growth / 1024 / 1024:.1f} MB")
        pool._previous_memory = memory_info.rss
        
    except ImportError:
        print("❌ psutil not available - install for detailed memory analysis")

memory_resource_analysis(pool)
```

### Problem-Specific Solutions

#### Solving Low Hit Rate Issues

**Step 1: Identify Root Cause**
```python
def diagnose_low_hit_rate(pool):
    """Diagnose reasons for low hit rate."""
    stats = pool.get_basic_stats()
    config = pool.default_config
    
    creates = stats['counters'].get('creates', 0)
    reuses = stats['counters'].get('reuses', 0)
    hits = stats['counters'].get('hits', 0)
    misses = stats['counters'].get('misses', 0)
    
    print("=== Hit Rate Diagnosis ===")
    print(f"Creates: {creates}")
    print(f"Reuses: {reuses}")
    print(f"Current Hits: {hits}")
    print(f"Current Misses: {misses}")
    print(f"Pool Size (max): {config.max_objects_per_key}")
    print(f"TTL: {config.ttl_seconds}s")
    
    # Analyze patterns
    if creates > reuses * 2:
        print("🔍 High create/reuse ratio suggests:")
        print("  - Pool too small for demand")
        print("  - Objects expiring too quickly")
        print("  - Factory keys too granular")
    
    if misses > hits:
        print("🔍 High miss rate suggests:")
        print("  - Pool exhausted under load")
        print("  - Need larger pool size")

diagnose_low_hit_rate(pool)
```

**Step 2: Apply Solutions**
```python
def fix_low_hit_rate(pool):
    """Apply fixes for low hit rate."""
    print("\n=== Applying Hit Rate Fixes ===")
    
    # Solution 1: Increase pool size
    current_size = pool.default_config.max_objects_per_key
    recommended_size = int(current_size * 1.5)
    print(f"1. Increase max_objects_per_key from {current_size} to {recommended_size}")
    
    # Solution 2: Extend TTL
    current_ttl = pool.default_config.ttl_seconds
    recommended_ttl = int(current_ttl * 1.2)
    print(f"2. Extend TTL from {current_ttl}s to {recommended_ttl}s")
    
    # Solution 3: Check factory key generation
    print("3. Review factory get_key() method:")
    print("   - Are keys too specific?")
    print("   - Can similar objects share keys?")
    print("   - Consider bucketing strategies")
    
    # Apply changes
    pool.default_config.max_objects_per_key = recommended_size
    pool.default_config.ttl_seconds = recommended_ttl
    
    print("✅ Fixes applied - monitor for improvement")

fix_low_hit_rate(pool)
```

#### Solving High Latency Issues

**Step 1: Identify Bottlenecks**
```python
def diagnose_high_latency(pool):
    """Diagnose causes of high acquisition latency."""
    if not pool.performance_metrics:
        print("❌ Performance metrics required for latency diagnosis")
        return
    
    snapshot = pool.performance_metrics.create_snapshot()
    
    print("=== Latency Diagnosis ===")
    print(f"Average Time: {snapshot.avg_acquisition_time_ms:.2f}ms")
    print(f"P95 Time: {snapshot.p95_acquisition_time_ms:.2f}ms")
    print(f"P99 Time: {snapshot.p99_acquisition_time_ms:.2f}ms")
    
    # Identify likely causes
    if snapshot.lock_contention_rate > 0.2:
        print("🔍 High lock contention is increasing latency")
    
    config = pool.default_config
    if config.max_validation_attempts > 2:
        print(f"🔍 High validation attempts ({config.max_validation_attempts}) may cause delays")
    
    # Check if pool is frequently full
    stats = pool.get_basic_stats()
    if stats['counters'].get('creates', 0) > stats['counters'].get('reuses', 0):
        print("🔍 Frequent object creation suggests pool exhaustion")

diagnose_high_latency(pool)
```

**Step 2: Apply Latency Fixes**
```python
def fix_high_latency(pool):
    """Apply fixes for high latency."""
    print("\n=== Applying Latency Fixes ===")
    
    # Fix 1: Reduce validation attempts
    current_attempts = pool.default_config.max_validation_attempts
    if current_attempts > 2:
        pool.default_config.max_validation_attempts = 2
        print(f"1. Reduced validation attempts from {current_attempts} to 2")
    
    # Fix 2: Increase cleanup interval to reduce lock contention
    current_interval = pool.default_config.cleanup_interval_seconds
    new_interval = current_interval * 1.5
    pool.default_config.cleanup_interval_seconds = new_interval
    print(f"2. Increased cleanup interval from {current_interval}s to {new_interval}s")
    
    # Fix 3: Profile factory methods
    print("3. Profile factory methods:")
    print("   - Time create() method execution")
    print("   - Time validate() method execution")
    print("   - Time reset() method execution")
    print("   - Optimize slow methods")
    
    print("✅ Latency fixes applied")

fix_high_latency(pool)
```

#### Solving Memory Leak Issues

**Step 1: Detect Memory Leaks**
```python
def detect_memory_leaks(pool):
    """Detect potential memory leaks."""
    print("=== Memory Leak Detection ===")
    
    # Monitor over time
    import gc
    import weakref
    
    # Force garbage collection
    gc.collect()
    
    # Check for growing object counts
    stats = pool.get_basic_stats()
    print(f"Pooled objects: {stats.get('total_pooled_objects', 0)}")
    print(f"Active objects: {stats.get('active_objects_count', 0)}")
    
    # Check active manager for dead refs
    if hasattr(pool, 'active_manager'):
        try:
            dead_refs = pool.active_manager.cleanup_dead_weakrefs()
            if dead_refs > 0:
                print(f"🔍 Found {dead_refs} dead weak references")
        except:
            pass
    
    # Memory usage
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        print(f"Process memory: {memory_mb:.1f} MB")
    except ImportError:
        print("Install psutil for memory monitoring")

detect_memory_leaks(pool)
```

**Step 2: Fix Memory Leaks**
```python
def fix_memory_leaks(pool):
    """Apply memory leak fixes."""
    print("\n=== Memory Leak Fixes ===")
    
    # Fix 1: Force cleanup
    print("1. Performing comprehensive cleanup...")
    if hasattr(pool, 'operations_manager'):
        expired_count = pool.operations_manager.cleanup_expired_objects()
        print(f"   Cleaned {expired_count} expired objects")
    
    if hasattr(pool, 'active_manager'):
        dead_refs = pool.active_manager.cleanup_dead_weakrefs()
        print(f"   Cleaned {dead_refs} dead weak references")
    
    # Fix 2: Reduce TTL for faster cleanup
    current_ttl = pool.default_config.ttl_seconds
    if current_ttl > 300:  # If > 5 minutes
        pool.default_config.ttl_seconds = 300
        print(f"2. Reduced TTL from {current_ttl}s to 300s for faster cleanup")
    
    # Fix 3: Review factory reset method
    print("3. Review factory implementation:")
    print("   - Ensure reset() clears all data structures")
    print("   - Implement destroy() for resource cleanup")
    print("   - Check for circular references")
    
    # Fix 4: Force garbage collection
    import gc
    collected = gc.collect()
    print(f"4. Garbage collection freed {collected} objects")
    
    print("✅ Memory leak fixes applied")

fix_memory_leaks(pool)
```

#### Solving Corruption Issues

**Step 1: Analyze Corruption Patterns**
```python
def analyze_corruption(pool):
    """Analyze object corruption patterns."""
    print("=== Corruption Analysis ===")
    
    stats = pool.get_basic_stats()
    corrupted = stats['counters'].get('corrupted', 0)
    validation_failures = stats['counters'].get('validation_failures', 0)
    
    print(f"Corrupted objects: {corrupted}")
    print(f"Validation failures: {validation_failures}")
    
    if corrupted > 0:
        print("🔍 Corruption detected - possible causes:")
        print("   - Thread safety issues in factory methods")
        print("   - Incomplete reset() implementation")
        print("   - External modification of pooled objects")
        print("   - Factory validate() method too strict")
    
    # Check corruption threshold
    threshold = pool.default_config.max_corrupted_objects
    print(f"Corruption threshold: {threshold}")
    
    if corrupted >= threshold:
        print("⚠️  Corruption threshold exceeded")

analyze_corruption(pool)
```

**Step 2: Fix Corruption Issues**
```python
def fix_corruption(pool):
    """Apply corruption fixes."""
    print("\n=== Corruption Fixes ===")
    
    # Fix 1: Review factory thread safety
    print("1. Factory Thread Safety Review:")
    print("   - Ensure factory methods are thread-safe")
    print("   - Avoid shared mutable state in factory")
    print("   - Use locks if necessary in factory methods")
    
    # Fix 2: Improve validation
    print("2. Validation Improvements:")
    print("   - Review validate() method logic")
    print("   - Make validation less strict if appropriate")
    print("   - Add better error handling in validate()")
    
    # Fix 3: Enhance reset method
    print("3. Reset Method Enhancement:")
    print("   - Ensure reset() fully clears object state")
    print("   - Test reset with various object states")
    print("   - Add validation after reset")
    
    # Fix 4: Increase validation attempts for transient issues
    current_attempts = pool.default_config.max_validation_attempts
    if current_attempts == 1:
        pool.default_config.max_validation_attempts = 2
        print(f"4. Increased validation attempts from 1 to 2")
    
    print("✅ Corruption fixes applied")

fix_corruption(pool)
```

## Preventive Measures

### Proactive Monitoring Setup

```python
def setup_proactive_monitoring(pool):
    """Set up comprehensive proactive monitoring."""
    print("=== Setting Up Proactive Monitoring ===")
    
    # 1. Enable comprehensive metrics
    pool.default_config.enable_performance_metrics = True
    pool.default_config.enable_acquisition_tracking = True
    pool.default_config.enable_lock_contention_tracking = True
    
    # 2. Set up diagnostic monitoring
    diagnostic = PoolDiagnostic(pool)
    
    # 3. Set up real-time monitoring
    monitor = RealTimeMonitor(pool, interval=300)  # 5 minutes
    monitor.start()
    
    # 4. Set up periodic health checks
    def periodic_health_check():
        while True:
            time.sleep(1800)  # Every 30 minutes
            health = pool.get_health_status()
            if health['status'] != 'healthy':
                print(f"⚠️  Health check failed: {health['status']}")
                report = diagnostic.generate_comprehensive_report()
                for issue in report.issues_found:
                    print(f"   - {issue}")
    
    health_thread = threading.Thread(target=periodic_health_check, daemon=True)
    health_thread.start()
    
    print("✅ Proactive monitoring configured")
    return diagnostic, monitor

diagnostic, monitor = setup_proactive_monitoring(pool)
```

### Configuration Best Practices

```python
def apply_best_practice_config(pool, environment='production'):
    """Apply best practice configuration for environment."""
    print(f"=== Applying Best Practices for {environment} ===")
    
    if environment == 'production':
        # Production settings
        pool.default_config.enable_performance_metrics = True
        pool.default_config.enable_logging = False  # Disable debug logging
        pool.default_config.max_validation_attempts = 2
        pool.default_config.cleanup_interval_seconds = 300.0  # 5 minutes
        pool.default_config.max_corrupted_objects = 5
        
    elif environment == 'development':
        # Development settings
        pool.default_config.enable_performance_metrics = True
        pool.default_config.enable_logging = True
        pool.default_config.max_validation_attempts = 3
        pool.default_config.cleanup_interval_seconds = 60.0  # 1 minute
        pool.default_config.max_corrupted_objects = 1  # Strict
        
    elif environment == 'testing':
        # Testing settings
        pool.default_config.enable_performance_metrics = False  # Faster tests
        pool.default_config.enable_logging = True
        pool.default_config.max_validation_attempts = 1
        pool.default_config.cleanup_interval_seconds = 10.0
        pool.default_config.max_corrupted_objects = 0  # Very strict
    
    print(f"✅ {environment} configuration applied")

apply_best_practice_config(pool, 'production')
```

## Case Studies

### Case Study 1: E-commerce Platform

**Problem:** High latency in product image processing during peak traffic
**Symptoms:** 
- Average acquisition time: 150ms
- High lock contention: 45%
- Low hit rate: 35%

**Diagnosis Process:**
```python
# Initial assessment revealed pool exhaustion
diagnostic = PoolDiagnostic(pool, "image_processor")
report = diagnostic.generate_comprehensive_report()

# Found: Pool size (20) too small for peak load (100+ concurrent requests)
# Found: Image factory create() method taking 100ms average
# Found: TTL too short (60s) for expensive image objects
```

**Solution Applied:**
```python
# 1. Increased pool size
pool.default_config.max_objects_per_key = 100

# 2. Extended TTL for expensive objects
pool.default_config.ttl_seconds = 1800  # 30 minutes

# 3. Optimized factory create method
# - Added image size bucketing in get_key()
# - Improved image creation algorithm

# 4. Reduced lock contention
pool.default_config.cleanup_interval_seconds = 600  # 10 minutes
```

**Results:**
- Average acquisition time: 25ms (83% improvement)
- Lock contention: 12% (73% improvement)  
- Hit rate: 78% (123% improvement)

### Case Study 2: Database Connection Pool

**Problem:** Memory leak in microservice connection pool
**Symptoms:**
- Memory usage growing 50MB/hour
- Pool size increasing continuously
- Occasional connection failures

**Diagnosis Process:**
```python
# Memory analysis showed connections not being properly cleaned up
def diagnose_connection_leak():
    # Found: Factory reset() not closing database transactions
    # Found: Weak references not being cleaned up
    # Found: Connection objects holding circular references
```

**Solution Applied:**
```python
# 1. Fixed factory reset method
def reset(self, connection):
    try:
        if connection.in_transaction():
            connection.rollback()
        connection.reset()  # Clear session state
        return True
    except:
        return False

# 2. Added proper destroy method
def destroy(self, connection):
    try:
        connection.close()
    except:
        pass

# 3. Reduced TTL and increased cleanup frequency
pool.default_config.ttl_seconds = 300  # 5 minutes
pool.default_config.cleanup_interval_seconds = 60  # 1 minute
```

**Results:**
- Memory leak eliminated
- Stable pool size
- Improved connection reliability

This comprehensive troubleshooting guide provides systematic approaches for identifying, diagnosing, and resolving issues in production environments. Regular monitoring and proactive maintenance prevent most problems before they impact users.
