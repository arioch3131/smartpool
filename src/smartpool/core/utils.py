"""
Safe logging utilities.

This module contains utility functions for robust and secure log management,
handling exceptions that may occur during log message writing.
"""

import logging
import sys
from typing import Any


def safe_log(logger: logging.Logger, level: int, message: str, *args: Any, **kwargs: Any) -> None:
    """Safely logs a message with fallback to stderr"""
    try:
        if logger and logger.isEnabledFor(level):
            logger.log(level, message, *args, **kwargs)
    except (ValueError, OSError):
        # Known recoverable errors, silently ignore
        pass
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Fallback: write to stderr if logging fails.
        try:
            sys.stderr.write(f"SmartPool logging fallback failure: {exc}\n")
        except (ValueError, OSError):
            return
