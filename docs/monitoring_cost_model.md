# Monitoring Cost Model

This document describes the runtime tradeoffs of SmartPool metrics modes.

## Modes

- `sync`: metrics are collected on the caller thread. Highest consistency, highest hot-path cost.
- `async`: metrics are queued and aggregated by a worker thread. Eventually consistent.
- `sampled`: same as `async`, but only one event out of `metrics_sample_rate` is retained.
- `off`: metrics and monitoring disabled.

## Configuration

```python
from smartpool.config import MemoryConfig, MetricsMode, MetricsOverloadPolicy

config = MemoryConfig(
    enable_performance_metrics=True,
    metrics_mode=MetricsMode.ASYNC,              # SYNC | ASYNC | SAMPLED
    metrics_queue_maxsize=20_000,                # bounded queue
    metrics_sample_rate=10,                      # used when mode=SAMPLED
    metrics_flush_timeout_seconds=2.0,           # best-effort shutdown flush
    metrics_overload_policy=MetricsOverloadPolicy.DROP_NEWEST,
)
```

## Overload Policy

- `drop_newest`: drops incoming events when queue is full.
- `drop_oldest`: evicts an old queued event to keep fresh data.
- `backpressure`: briefly blocks producer before dropping.

Health counters/gauges exposed by the pool:

- `metrics_events_dropped` (counter)
- `metrics_worker_errors` (counter)
- `metrics_queue_depth` (gauge)
- `metrics_worker_alive` (gauge)

## Consistency and Shutdown

- `async` and `sampled` are eventually consistent by design.
- `shutdown()` performs best-effort flush using `metrics_flush_timeout_seconds`.
- On timeout/saturation, metric loss is expected and tracked via counters.

## Current Benchmark Snapshot (2026-04-11)

Command used:

```bash
python3 scripts/benchmark_metrics_modes.py --iterations 10000 --repeats 5 --warmup 1
```

Median runtime on local machine:

- `off`: `161.26ms` (baseline)
- `sync`: `401.66ms` (`+149.1%` overhead vs off)
- `async`: `360.38ms` (`+123.5%`)
- `sampled`: `211.67ms` (`+31.3%`)

Interpretation:

- `async` now outperforms `sync` for this workload, but still has substantial overhead.
- `sampled` provides the best compromise currently.
- The project target (`<= 10-15%` overhead) is not yet met.

## Production Recommendation (current state)

- Default to `MetricsMode.SAMPLED` for hot paths.
- Use `metrics_sample_rate` between `5` and `20` under sustained load.
- Track `metrics_events_dropped` and `metrics_queue_depth`; increase queue or sample more aggressively if needed.
- Use `sync` mainly for debugging or when strict immediacy is required.

## Quick Mode Selection

Use this as a practical decision tree:

1. Need strict, immediate per-operation metrics in the caller thread?
   - Choose `sync`.
2. Need low overhead in production while keeping metrics stable enough for adaptive behavior?
   - Choose `sampled` (start at `metrics_sample_rate=10`).
3. Need near full-fidelity metrics without synchronous hot-path updates?
   - Choose `async` and tune queue size/policy.
4. Running throughput baselines where instrumentation must be minimized?
   - Set `enable_performance_metrics=False` (`off`).

## Auto-Tuning Note

- Auto-tuning should be evaluated with percentile stability (`p95`, `p99`) in addition to averages.
- A bounded sliding history (`max_performance_history_size`) is generally preferred to react faster to load changes.
- Monitor queue pressure (`metrics_queue_depth`) and drops (`metrics_events_dropped`) to detect under-sampling or saturation.
