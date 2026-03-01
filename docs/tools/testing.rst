Testing Tools
=============

This section provides an overview of the testing strategy and tools used within the `smartpool` project.

Testing Framework
-----------------

The project uses `pytest` as its primary testing framework for unit, integration, and performance tests.

Running Tests
-------------

The project currently provides separate scripts for each test scope:

.. code-block:: bash

   # Static checks + core unit tests
   bash scripts/run_src_unit_tests.sh

   # Integration tests
   bash scripts/run_integration_tests.sh

   # Performance tests
   bash scripts/run_benchmarks_tests.sh

Individual Test Execution
--------------------------

If you wish to run specific types of tests, you can use `pytest` directly:

- **Unit Tests:**

  .. code-block:: bash

     pytest tests/unit/core/

- **Integration Tests:**

  .. code-block:: bash

     pytest tests/integration/

Static Analysis
---------------

In addition to runtime tests, the project employs static analysis tools to ensure code quality and identify potential issues early:

- **Ruff security rules (`S`)**: Used for identifying common security issues in Python code.

  .. code-block:: bash

     ruff check --select S --ignore S311 src/

- **MyPy:** For static type checking to catch type-related errors.

  .. code-block:: bash

     mypy src/
