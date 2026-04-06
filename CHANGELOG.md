# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

### Added
- Placeholder for upcoming changes.

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
