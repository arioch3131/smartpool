Installation
============

This guide provides instructions on how to install `smartpool` and its optional dependencies.

Prerequisites
-------------
`smartpool` requires Python 3.11 or newer.

Basic Installation
------------------
You can install the latest stable version of `smartpool` using pip:

.. code-block:: bash

   pip install smartpool

Installation with Optional Dependencies
---------------------------------------
`smartpool` offers several optional dependencies for extended functionality. You can install them individually or all at once.

To install all optional dependencies:

.. code-block:: bash

   pip install smartpool[all]

To install specific optional dependencies (e.g., for imaging and database support):

.. code-block:: bash

   pip install smartpool[imaging,database]

Available optional dependency groups:

- ``imaging``: For image processing factories (requires Pillow).
- ``qt``: For PyQt-related factories (requires PyQt6).
- ``scientific``: For scientific computing factories (requires numpy).
- ``database``: For database-related factories (requires SQLAlchemy).
- ``security``: For security analysis tools (requires bandit, safety).
- ``quality``: For code quality tools (requires pre-commit, commitizen).
- ``dev``: All development dependencies (includes security, quality, and testing tools).
- ``examples``: Dependencies required to run the examples.

Installation from Source (using a built wheel)
----------------------------------------------
If you want to install `smartpool` from a locally built wheel file, follow these steps:

1.  **Build the wheel:**
    Navigate to the project's root directory and run the `build_wheel.sh` script:

    .. code-block:: bash

       bash scripts/build_wheel.sh

    This will generate a wheel file (e.g., `smartpool-1.0.0-py3-none-any.whl`) in the `dist/` directory.

2.  **Install the wheel:**
    Use pip to install the generated wheel file:

    .. code-block:: bash

       pip install dist/smartpool-1.0.0-py3-none-any.whl

    Replace `smartpool-1.0.0-py3-none-any.whl` with the actual filename of the wheel.
