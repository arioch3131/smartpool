Scripts and Tools
=================

This section documents the various utility scripts available in the ``scripts/`` directory.
These scripts automate common development, testing, and build tasks.

Available Scripts
-----------------

- **``build_docs.sh``**
  Builds the project's Sphinx documentation. This script compiles the reStructuredText source files into HTML documentation.

  .. code-block:: bash

     bash scripts/build_docs.sh

- **``build_wheel.sh``**
  Builds the Python distribution packages (wheel and sdist) for the `smartpool` library.

  .. code-block:: bash

     bash scripts/build_wheel.sh

- **``run_examples_tests.sh``**
  Runs security linting (Ruff `S` rules) and unit tests for example factories.

  .. code-block:: bash

     bash scripts/run_examples_tests.sh

- **``run_formatters.sh``**
  Runs formatting and linting for source and tests using Ruff.

  .. code-block:: bash

     bash scripts/run_formatters.sh

- **``run_src_unit_tests.sh``**
  Runs static analysis (`mypy`, Ruff security checks) and unit tests for the core code.

  .. code-block:: bash

     bash scripts/run_src_unit_tests.sh

- **``run_integration_tests.sh``**
  Runs integration tests with coverage reporting.

  .. code-block:: bash

     bash scripts/run_integration_tests.sh

- **``run_benchmarks_tests.sh``**
  Runs performance tests from `tests/performance/`.

  .. code-block:: bash

     bash scripts/run_benchmarks_tests.sh

Script Usage
------------

To execute any of these scripts, navigate to the project root directory and run the script using `bash`:

.. code-block:: bash

   bash scripts/script_name.sh

For more details on a specific script's functionality, you can often inspect its content directly.
