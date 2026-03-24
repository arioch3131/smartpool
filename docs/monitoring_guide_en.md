# Monitoring & Metrics Guide

## Overview

The Adaptive Memory Pool system provides comprehensive monitoring and metrics capabilities for production environments. This guide covers performance metrics collection, health monitoring, alerting systems, dashboard integration, and real-time monitoring approaches.

## Metrics Collection System

### Enabling Performance Metrics

Performance metrics are the foundation of monitoring. Enable them in your pool configuration:

```python
from smartpool.config import MemoryConfig
from smartpool.core.smartpool_manager import SmartObjectManager

# Enable comprehensive metrics collection
config = MemoryConfig(
    enable_performance_metrics=True,     # Enable metrics collection
    enable_acquisition_tracking=True,        # Track detailed timing
    enable_lock_contention_tracking=True,         # Monitor threading issues
    max_performance_history_size=2000       # Retain 2000 historical samples
)

pool = SmartObjectManager(factory, default_config=config)
```

### Core Metrics Types

#### Performance Snapshot
Real-time performance data captured at a specific moment:

```python
# Get current performance snapshot
snapshot = pool.performance_metrics.create_snapshot()

print(f"Total acquisitions: {snapshot.total_acquisitions}")
print(f"Hit rate: {snapshot.hit_rate:.2%}")
print(f"Average acquisition time: {snapshot.avg_acquisition_time_ms:.2f}ms")
print(f"95th percentile time: {snapshot.p95_acquisition_time_ms:.2f}ms")
print(f"Throughput: {snapshot.acquisitions_per_second:.1f} ops/sec")
print(f"Lock contention rate: {snapshot.lock_contention_rate:.2%}")
```

#### Key Performance Indicators

**Hit Rate**
- Definition: Percentage of requests served from pool vs creating new objects
- Formula: `reuses / (creates + reuses)`
- Target: > 60% (general), > 80% (high-performance applications)

**Acquisition Time**
- Definition: Time to acquire an object from the pool
- Metrics: Average, P95, P99, Min/Max
- Target: < 20ms average, < 50ms P95

**Throughput**
- Definition: Operations per second
- Calculation: Acquisitions in recent time window
- Usage: Capacity planning and load analysis

**Lock Contention Rate**
- Definition: Percentage of acquisitions experiencing lock contention
- Target: < 20% for healthy systems
- Critical threshold: > 40%

### Historical Tracking

The system maintains historical performance data for trend analysis:

```python
# Get comprehensive performance report with trends
report = pool.performance_metrics.get_performance_report(last_n_snapshots=20)

print("=== Current Metrics ===")
current = report['current_metrics']
print(f"Hit rate: {current['hit_rate']:.2%}")
print(f"Average time: {current['avg_acquisition_time_ms']:.2f}ms")

print("\n=== Trends (last 20 snapshots) ===")
trends = report['trends']
hit_rates = trends['hit_rate_trend']
if len(hit_rates) > 1:
    trend_direction = "↑" if hit_rates[-1] > hit_rates[0] else "↓"
    print(f"Hit rate trend: {hit_rates[0]:.2%} → {hit_rates[-1]:.2%} {trend_direction}")

print("\n=== Alerts ===")
for alert in report['alerts']:
    print(f"⚠️  {alert['metric']}: {alert['message']} (severity: {alert['severity']})")

print("\n=== Recommendations ===")
for rec in report['recommendations']:
    print(f"💡 {rec['area']}: {rec['suggestion']}")
```

## Health Monitoring

### Health Status Assessment

The system automatically evaluates pool health based on multiple factors:

```python
# Get comprehensive health status
health = pool.get_health_status()

print(f"Overall Status: {health['status'].upper()}")  # healthy/warning/critical
print(f"Hit Rate: {health['hit_rate']:.2%}")
print(f"Corruption Rate: {health['corruption_rate']:.2%}")
print(f"Total Requests: {health['total_requests']}")
print(f"Pooled Objects: {health['total_pooled_objects']}")
print(f"Active Objects: {health['active_objects_count']}")

if health['issues']:
    print("\n🚨 Issues Detected:")
    for issue in health['issues']:
        print(f"  - {issue}")
```

### Health Status Levels

#### Healthy
- Hit rate > 30%
- Corruption rate < 10%  
- No critical validation failures
- Normal operation indicators

#### Warning
- One minor issue detected
- Hit rate 20-30%
- Slight increase in corruption rate
- Requires monitoring

#### Critical
- Multiple issues detected
- Hit rate < 20%
- High corruption rate (> 10%)
- Frequent validation failures
- Immediate attention required

### Custom Health Thresholds

Configure custom health assessment thresholds:

```python
# Custom health monitoring with specific thresholds
class CustomHealthMonitor:
    def __init__(self, pool, thresholds=None):
        self.pool = pool
        self.thresholds = thresholds or {
            'min_hit_rate': 0.4,           # 40% minimum hit rate
            'max_corruption_rate': 0.05,   # 5% maximum corruption
            'max_avg_time_ms': 25.0,       # 25ms maximum average time
            'max_lock_contention': 0.3     # 30% maximum lock contention
        }
    
    def assess_health(self):
        stats = self.pool.get_basic_stats()
        health = self.pool.get_health_status()
        issues = []
        
        # Check hit rate
        if health['hit_rate'] < self.thresholds['min_hit_rate']:
            issues.append(f"Hit rate {health['hit_rate']:.1%} below {self.thresholds['min_hit_rate']:.1%}")
        
        # Check response time if metrics available
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            if snapshot.avg_acquisition_time_ms > self.thresholds['max_avg_time_ms']:
                issues.append(f"Average response time {snapshot.avg_acquisition_time_ms:.1f}ms too high")
        
        # Determine status
        if not issues:
            status = "healthy"
        elif len(issues) == 1:
            status = "warning"
        else:
            status = "critical"
        
        return {
            'status': status,
            'issues': issues,
            'timestamp': time.time()
        }

# Usage
monitor = CustomHealthMonitor(pool)
health = monitor.assess_health()
```

## Dashboard Integration

### Dashboard Summary

Get formatted metrics for dashboard display:

```python
# Get dashboard-ready metrics
dashboard = pool.manager.get_dashboard_summary()

print("=== Pool Dashboard ===")
print(f"Status: {dashboard['status']}")
print(f"Preset: {dashboard['preset']}")

metrics = dashboard['metrics']
print(f"Hit Rate: {metrics['hit_rate']:.1%}")
print(f"Pooled Objects: {metrics['total_pooled_objects']}")
print(f"Active Objects: {metrics['active_objects_count']}")
print(f"Total Creates: {metrics['total_creates']}")
print(f"Total Reuses: {metrics['total_reuses']}")

# Advanced metrics if available
if 'advanced_metrics' in dashboard:
    adv = dashboard['advanced_metrics']
    print(f"Avg Response Time: {adv['avg_response_time_ms']:.1f}ms")
    print(f"P95 Response Time: {adv['p95_response_time_ms']:.1f}ms")
    print(f"Throughput: {adv['throughput_ops_sec']:.1f} ops/sec")
    print(f"Lock Contention: {adv['lock_contention_rate']:.1%}")

# Alert counts
print(f"Active Alerts: {dashboard.get('alerts', 0)}")
print(f"Warnings: {dashboard.get('warnings', 0)}")
```

### Web Dashboard Integration

Create REST API endpoints for web monitoring:

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/api/pools/status")
async def get_pool_status():
    """Get overall pool health status."""
    health = pool.get_health_status()
    
    if health['status'] == 'critical':
        return JSONResponse(content=health, status_code=503)
    elif health['status'] == 'warning':
        return JSONResponse(content=health, status_code=200)
    else:
        return health

@app.get("/api/pools/dashboard")
async def get_dashboard():
    """Get dashboard metrics."""
    return pool.manager.get_dashboard_summary()

@app.get("/api/pools/metrics")
async def get_detailed_metrics():
    """Get detailed performance metrics."""
    if not pool.performance_metrics:
        return {"error": "Performance metrics not enabled"}
    
    report = pool.performance_metrics.get_performance_report()
    return {
        "current": report['current_metrics'],
        "trends": report['trends'],
        "alerts": report['alerts']
    }

@app.get("/api/pools/stats")
async def get_raw_stats():
    """Get raw statistics."""
    return pool.get_basic_stats()
```

## Alerting System

### Automatic Alert Generation

The system generates alerts based on performance thresholds:

```python
# Get current alerts from performance metrics
if pool.performance_metrics:
    report = pool.performance_metrics.get_performance_report()
    
    for alert in report['alerts']:
        severity = alert['severity']  # low, medium, high, critical
        metric = alert['metric']      # hit_rate, response_time, etc.
        message = alert['message']    # Human-readable description
        
        print(f"[{severity.upper()}] {metric}: {message}")
        
        # Take action based on severity
        if severity == 'critical':
            # Send immediate notification
            send_critical_alert(alert)
        elif severity == 'high':
            # Log and monitor
            logger.warning(f"High severity alert: {message}")
```

### Alert Types and Thresholds

#### Performance Alerts
- **Low Hit Rate**: < 50% hit rate (medium), < 30% (high)
- **High Response Time**: > 50ms average (medium), > 100ms (high)
- **High Lock Contention**: > 30% (medium), > 50% (critical)
- **Low Throughput**: Significant throughput degradation

#### Health Alerts
- **High Corruption Rate**: > 5% corruption rate
- **Validation Failures**: Frequent validation failures
- **Memory Leaks**: Continuously growing pool size
- **Thread Contention**: Excessive lock waiting

### Custom Alert Implementation

```python
import time
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class Alert:
    pool_name: str
    alert_type: str
    severity: str  # low, medium, high, critical
    message: str
    value: float
    threshold: float
    timestamp: float

class AlertManager:
    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {
            'hit_rate_low': 0.4,
            'response_time_high': 50.0,
            'lock_contention_high': 0.3,
            'corruption_rate_high': 0.05
        }
        self.active_alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
    
    def check_alerts(self, pool_name: str, pool) -> List[Alert]:
        """Check for alert conditions and return new alerts."""
        alerts = []
        
        # Get current metrics
        health = pool.get_health_status()
        
        # Check hit rate
        if health['hit_rate'] < self.thresholds['hit_rate_low']:
            severity = 'high' if health['hit_rate'] < 0.3 else 'medium'
            alerts.append(Alert(
                pool_name=pool_name,
                alert_type='low_hit_rate',
                severity=severity,
                message=f"Hit rate {health['hit_rate']:.1%} below threshold",
                value=health['hit_rate'],
                threshold=self.thresholds['hit_rate_low'],
                timestamp=time.time()
            ))
        
        # Check response time if metrics available
        if pool.performance_metrics:
            snapshot = pool.performance_metrics.create_snapshot()
            
            if snapshot.avg_acquisition_time_ms > self.thresholds['response_time_high']:
                severity = 'critical' if snapshot.avg_acquisition_time_ms > 100 else 'high'
                alerts.append(Alert(
                    pool_name=pool_name,
                    alert_type='high_response_time',
                    severity=severity,
                    message=f"Response time {snapshot.avg_acquisition_time_ms:.1f}ms too high",
                    value=snapshot.avg_acquisition_time_ms,
                    threshold=self.thresholds['response_time_high'],
                    timestamp=time.time()
                ))
        
        return alerts
    
    def process_alerts(self, alerts: List[Alert]):
        """Process new alerts and take appropriate actions."""
        for alert in alerts:
            self.active_alerts.append(alert)
            self.alert_history.append(alert)
            
            # Take action based on severity
            if alert.severity == 'critical':
                self.send_critical_notification(alert)
            elif alert.severity == 'high':
                self.send_high_priority_notification(alert)
            else:
                self.log_alert(alert)
    
    def send_critical_notification(self, alert: Alert):
        """Send immediate notification for critical alerts."""
        # Implement your notification system
        print(f"🚨 CRITICAL ALERT: {alert.message}")
        # Could send email, Slack message, PagerDuty alert, etc.
    
    def send_high_priority_notification(self, alert: Alert):
        """Send high priority notification."""
        print(f"⚠️  HIGH PRIORITY: {alert.message}")
        # Could send to monitoring system, team chat, etc.
    
    def log_alert(self, alert: Alert):
        """Log lower priority alerts."""
        print(f"📝 ALERT: {alert.message}")

# Usage
alert_manager = AlertManager()

def monitor_pool():
    """Periodic monitoring function."""
    alerts = alert_manager.check_alerts("main_pool", pool)
    if alerts:
        alert_manager.process_alerts(alerts)

# Run monitoring periodically
import threading
def monitoring_loop():
    while True:
        monitor_pool()
        time.sleep(60)  # Check every minute

monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
monitor_thread.start()
```

## Real-Time Monitoring

### Continuous Monitoring Setup

```python
import time
import threading
from collections import deque

class RealTimeMonitor:
    def __init__(self, pool, update_interval=5.0):
        self.pool = pool
        self.update_interval = update_interval
        self.running = False
        self.monitor_thread = None
        self.metrics_history = deque(maxlen=100)  # Keep last 100 samples
        self.callbacks = []
    
    def add_callback(self, callback):
        """Add callback function to receive real-time updates."""
        self.callbacks.append(callback)
    
    def start(self):
        """Start real-time monitoring."""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("Real-time monitoring started")
    
    def stop(self):
        """Stop real-time monitoring."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("Real-time monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                # Collect current metrics
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # Call all registered callbacks
                for callback in self.callbacks:
                    try:
                        callback(metrics)
                    except Exception as e:
                        print(f"Callback error: {e}")
                
                time.sleep(self.update_interval)
            
            except Exception as e:
                print(f"Monitor loop error: {e}")
                time.sleep(self.update_interval)
    
    def _collect_metrics(self):
        """Collect current metrics snapshot."""
        health = self.pool.get_health_status()
        stats = self.pool.get_basic_stats()
        
        metrics = {
            'timestamp': time.time(),
            'status': health['status'],
            'hit_rate': health['hit_rate'],
            'corruption_rate': health['corruption_rate'],
            'total_pooled_objects': health['total_pooled_objects'],
            'active_objects_count': health['active_objects_count'],
            'total_requests': health['total_requests']
        }
        
        # Add performance metrics if available
        if self.pool.performance_metrics:
            snapshot = self.pool.performance_metrics.create_snapshot()
            metrics.update({
                'avg_acquisition_time_ms': snapshot.avg_acquisition_time_ms,
                'p95_acquisition_time_ms': snapshot.p95_acquisition_time_ms,
                'throughput_ops_sec': snapshot.acquisitions_per_second,
                'lock_contention_rate': snapshot.lock_contention_rate
            })
        
        return metrics
    
    def get_recent_metrics(self, n=10):
        """Get recent metrics history."""
        return list(self.metrics_history)[-n:]

# Usage example
def print_metrics_callback(metrics):
    """Simple callback to print metrics."""
    print(f"[{time.strftime('%H:%M:%S')}] "
          f"Hit Rate: {metrics['hit_rate']:.1%} | "
          f"Active: {metrics['active_objects_count']} | "
          f"Status: {metrics['status']}")

def alert_callback(metrics):
    """Callback to check for alert conditions."""
    if metrics['hit_rate'] < 0.5:
        print(f"⚠️  Low hit rate alert: {metrics['hit_rate']:.1%}")
    
    if metrics.get('avg_acquisition_time_ms', 0) > 50:
        print(f"⚠️  High latency alert: {metrics['avg_acquisition_time_ms']:.1f}ms")

# Setup real-time monitoring
monitor = RealTimeMonitor(pool, update_interval=10.0)  # Every 10 seconds
monitor.add_callback(print_metrics_callback)
monitor.add_callback(alert_callback)

# Start monitoring
monitor.start()

# Later, stop monitoring
# monitor.stop()
```

## Key Statistics and Per-Key Metrics

### Pool-Level Statistics

```python
# Get comprehensive pool statistics
stats = pool.get_basic_stats()

print("=== Pool Statistics ===")
print(f"Total creates: {stats['counters'].get('creates', 0)}")
print(f"Total reuses: {stats['counters'].get('reuses', 0)}")
print(f"Current hits: {stats['counters'].get('hits', 0)}")
print(f"Current misses: {stats['counters'].get('misses', 0)}")
print(f"Pooled objects: {stats.get('total_pooled_objects', 0)}")
print(f"Active objects: {stats.get('active_objects_count', 0)}")
print(f"Corrupted objects: {stats['counters'].get('corrupted', 0)}")
print(f"Validation failures: {stats['counters'].get('validation_failures', 0)}")
```

### Per-Key Performance Analysis

```python
# Get detailed per-key statistics
if pool.performance_metrics:
    report = pool.performance_metrics.get_performance_report()
    
    print("\n=== Top Keys by Usage ===")
    for key, usage_count in report['current_metrics']['top_keys_by_usage']:
        print(f"{key}: {usage_count} acquisitions")
    
    print("\n=== Slowest Keys ===")
    for key, avg_time in report['current_metrics']['slowest_keys']:
        print(f"{key}: {avg_time:.2f}ms average")

# Get key-specific statistics if available
def get_key_statistics():
    """Get per-key performance statistics."""
    if hasattr(pool.performance_metrics, 'get_key_statistics'):
        key_stats = pool.performance_metrics.get_key_statistics()
        
        for key, stats in key_stats.items():
            print(f"\nKey: {key}")
            print(f"  Usage count: {stats['usage_count']}")
            print(f"  Hit rate: {stats['hit_rate']:.2%}")
            print(f"  Average time: {stats['avg_time_ms']:.2f}ms")
            print(f"  Total time: {stats['total_time_ms']:.1f}ms")

get_key_statistics()
```

## Production Monitoring Best Practices

### Monitoring Checklist

#### Essential Metrics to Monitor
- **Hit Rate**: Primary efficiency indicator
- **Response Time**: P50, P95, P99 percentiles  
- **Throughput**: Operations per second
- **Error Rates**: Validation failures, corruption rates
- **Resource Usage**: Active objects, memory consumption

#### Recommended Alert Thresholds
- **Hit Rate**: Warning < 60%, Critical < 40%
- **Response Time**: Warning > 20ms avg, Critical > 50ms avg
- **Lock Contention**: Warning > 20%, Critical > 40%
- **Corruption Rate**: Warning > 1%, Critical > 5%

#### Monitoring Frequency
- **Real-time Dashboard**: 5-10 second updates
- **Alert Checks**: 1-2 minute intervals
- **Historical Reports**: Hourly/daily aggregations
- **Health Checks**: 30-60 second intervals

### Integration with Monitoring Systems

#### Prometheus/Grafana Integration

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

class PrometheusMetrics:
    def __init__(self):
        # Counters
        self.acquisitions_total = Counter('pool_acquisitions_total', 'Total acquisitions', ['pool', 'result'])
        self.corrupted_objects_total = Counter('pool_corrupted_objects_total', 'Corrupted objects', ['pool'])
        
        # Histograms
        self.acquisition_duration = Histogram('pool_acquisition_duration_seconds', 'Acquisition time', ['pool'])
        
        # Gauges
        self.hit_rate = Gauge('pool_hit_rate', 'Current hit rate', ['pool'])
        self.active_objects_count = Gauge('pool_active_objects_count', 'Active objects', ['pool'])
        self.total_pooled_objects = Gauge('pool_total_pooled_objects', 'Pooled objects', ['pool'])
    
    def update_from_pool(self, pool_name, pool):
        """Update Prometheus metrics from pool state."""
        health = pool.get_health_status()
        stats = pool.get_basic_stats()
        
        # Update gauges
        self.hit_rate.labels(pool=pool_name).set(health['hit_rate'])
        self.active_objects_count.labels(pool=pool_name).set(health['active_objects_count'])
        self.total_pooled_objects.labels(pool=pool_name).set(health['total_pooled_objects'])

# Start Prometheus metrics server
prometheus_metrics = PrometheusMetrics()
start_http_server(8000)  # Metrics available at http://localhost:8000/metrics

# Update metrics periodically
def update_prometheus_metrics():
    prometheus_metrics.update_from_pool("main_pool", pool)

# Schedule regular updates
import threading
import time

def prometheus_update_loop():
    while True:
        update_prometheus_metrics()
        time.sleep(10)  # Update every 10 seconds

prometheus_thread = threading.Thread(target=prometheus_update_loop, daemon=True)
prometheus_thread.start()
```

#### Logging Integration

```python
import logging
import json

# Setup structured logging for metrics
metrics_logger = logging.getLogger('pool.metrics')
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
metrics_logger.addHandler(handler)
metrics_logger.setLevel(logging.INFO)

def log_metrics_periodically():
    """Log metrics in structured format."""
    health = pool.get_health_status()
    
    metrics_data = {
        'timestamp': time.time(),
        'pool_status': health['status'],
        'hit_rate': health['hit_rate'],
        'corruption_rate': health['corruption_rate'],
        'active_objects_count': health['active_objects_count'],
        'total_pooled_objects': health['total_pooled_objects'],
        'total_requests': health['total_requests']
    }
    
    if pool.performance_metrics:
        snapshot = pool.performance_metrics.create_snapshot()
        metrics_data.update({
            'avg_acquisition_time_ms': snapshot.avg_acquisition_time_ms,
            'p95_acquisition_time_ms': snapshot.p95_acquisition_time_ms,
            'throughput_ops_sec': snapshot.acquisitions_per_second
        })
    
    metrics_logger.info(json.dumps(metrics_data))

# Log metrics every 5 minutes
def metrics_logging_loop():
    while True:
        log_metrics_periodically()
        time.sleep(300)  # 5 minutes

logging_thread = threading.Thread(target=metrics_logging_loop, daemon=True)
logging_thread.start()
```

This comprehensive monitoring and metrics system provides the observability needed for production deployments, enabling proactive performance management and rapid issue identification.