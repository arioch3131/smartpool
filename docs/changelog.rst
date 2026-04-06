Changelog
=========

Version history and changes.

Unreleased
----------

Added
~~~~~

- Placeholder for upcoming changes.

1.1.1 (2026-04-06)
------------------

Changed
~~~~~~~

- Additional hot-path optimizations in ``acquire()`` / ``release()`` without public API changes.
- Reduced lock contention and high-frequency stats overhead.
- Micro-optimizations in ``PoolOperationsManager`` for allocation/counter efficiency.

Fixed
~~~~~

- Improved shutdown resilience when object destruction fails during pool clear.
- Restored expected delegation/logging compatibility for existing tests and integrations.

Validation
~~~~~~~~~~

- Quality gates pass: ``ruff``, ``ruff format --check``, ``mypy``, ``pytest``.
- Benchmarks rerun at multiple sizes (``10k``, ``50k``, ``100k``) with stable gains.

1.1.0 (2026-04-06)
------------------

Changed
~~~~~~~

- Performance optimizations on hot paths (``acquire``/``release``) without public API changes.
- Replaced repeated pooled-object full scans with an incremental internal counter.
- Reduced redundant ``time.time()`` calls in critical sections.
- Reduced lock scope in ``release()`` by moving validation/reset work out of the pool lock.

1.0.0 (2026-03-24)
------------------

Added
~~~~~

- First public release of SmartPool.
- Core object pooling manager with configurable presets.
- Monitoring, performance metrics, and background cleanup foundations.
- Examples, tests, and base documentation.
