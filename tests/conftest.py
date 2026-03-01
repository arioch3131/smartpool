"""
This module contains shared fixtures, hooks, and other configurations for pytest.

By defining fixtures and hooks in this file, they become available to all test
modules within this directory and its subdirectories without needing to be
explicitly imported.

For more information on conftest.py, see the official pytest documentation:
https://docs.pytest.org/en/latest/reference/conftest.html
"""

import os
import sys

# Ensure Qt tests run in headless environments (CI and local shells without display).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Add the project root directory to the Python path.
# This allows tests to import modules from the 'src' and 'examples' directories
# as if they were running from the project root.
# os.path.dirname(__file__) gives the directory of the conftest.py file.
# os.path.join(..., '..') navigates up one level to the project root.
# os.path.abspath ensures the path is absolute.
# sys.path.insert(0, ...) adds the path to the beginning of the list, so it's
# checked first.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
