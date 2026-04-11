# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Added
- Placeholder for upcoming changes.

## [2.0.0] - 2026-04-11

### Added
- Metrics pipeline modes for monitoring cost control:
  - `MetricsMode.SYNC` (in-thread metrics)
  - `MetricsMode.ASYNC` (worker/queue-based aggregation)
  - `MetricsMode.SAMPLED` (async + sampling)
- Async metrics dispatcher with bounded queue, overload policies, best-effort flush, and health counters/gauges.
- New metrics configuration options in `MemoryConfig`:
  - `metrics_mode`
  - `metrics_queue_maxsize`
  - `metrics_sample_rate`
  - `metrics_flush_timeout_seconds`
  - `metrics_overload_policy`
- Benchmark and analysis tooling:
  - `scripts/benchmark_metrics_modes.py`
  - `scripts/compare_metrics_stats.py`
- New example for mode comparison:
  - `examples/example_11_metrics_modes.py`

### Changed
- `SmartObjectManager` now routes metrics events through sync/async/sampled paths based on `metrics_mode`.
- Added async-path protections under pressure (event filtering/coalescing) while preserving auto-tuning signal quality.
- Preset switching now reinitializes/shuts down metrics dispatcher safely when mode changes.
- Performance benchmark suite extended for auto-tuning scenarios and grouped runs.

### Documentation
- Expanded metrics mode guidance in:
  - `README.md`
  - `docs/user_guide/configuration.rst`
  - `docs/monitoring_cost_model.md`
- Added practical mode-selection guidance and configuration templates for production/debug workflows.

### Tests
- Expanded `metrics_dispatcher` unit coverage with branch-focused tests (queue overload behaviors, control events, worker edge paths).
- Added integration and manager-level tests for async/sampled metrics behavior and resiliency.

## [1.1.1] - 2026-04-06

### Changed
- Additional hot-path optimizations in `acquire()` / `release()` without public API changes.
- Reduced lock contention by moving more preparation work outside critical sections.
- Reduced overhead in high-frequency stats updates (batched counter increments).
- Micro-optimizations in `PoolOperationsManager` for allocation/counter efficiency.

### Fixed
- Improved shutdown resilience when object destruction fails during pool clear.
- Restored expected delegation/logging compatibility for existing tests and integrations.

### Validation
- Full quality gates pass: `ruff`, `ruff format --check`, `mypy`, `pytest` (`546 passed`).
- Benchmarks rerun at multiple sizes (`10k`, `50k`, `100k`) with stable gains.

## [1.1.0] - 2026-04-06

### Changed
- Performance optimizations on hot paths (`acquire`/`release`) without public API changes.
- Replaced repeated pooled-object full scans with an incremental internal counter.
- Reduced redundant `time.time()` calls in critical sections.
- Reduced redundant per-key config lookups during validation/corruption handling flows.
- Reduced lock scope in `release()` by moving validation/reset work out of the pool lock.
- Optimized `should_add_to_pool`/`add_to_pool` code paths to reduce overhead.

### Validation
- Full test suite passes (`546` tests).
- Benchmark reference improvement for `metrics_off` workload: ~13-14% faster vs v1.0.0 baseline.

## [1.0.0] - 2026-03-24

### Added
- First public release of SmartPool.
- Core object pooling manager with configurable presets.
- Monitoring, performance metrics, and background cleanup foundations.
- Examples, tests, and base documentation.
