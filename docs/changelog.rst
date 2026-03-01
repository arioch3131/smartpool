Changelog
=========

Version history and changes.

Unreleased (2026-03-01)
-----------------------

Examples
~~~~~~~~

- Standardized example execution commands to module form (``python -m examples.<module>``)
  in documentation and helper messages.
- Added ``examples/__init__.py`` to ensure reliable module-based execution.
- Improved optional dependency handling in example runners:

  - ``example_07_main_web_server.py`` now handles missing ``uvicorn`` gracefully.
  - ``example_09_debugging_troubleshooting.py`` now supports degraded mode when
    ``psutil`` is not installed.

- Added ``--quick`` mode to heavy examples for faster local validation:

  - ``example_04_numpy_arrays.py``
  - ``example_08_advanced_patterns.py``
  - ``example_09_debugging_troubleshooting.py``
  - ``example_10_complete_integration.py``

- Corrected FastAPI launch guidance in complete integration example and exposed a
  ``create_fastapi_app`` factory for Uvicorn.
- Cleaned noisy output in selected examples (reduced null-byte-heavy prints).

Dependencies
~~~~~~~~~~~~

- Updated ``[project.optional-dependencies].all`` in ``pyproject.toml`` to include
  all example-related dependencies:
  ``uvicorn``, ``fastapi``, ``Flask``, ``psutil``, ``requests``, ``python-multipart``.
