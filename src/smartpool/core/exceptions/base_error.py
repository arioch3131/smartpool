"""
SmartPool Custom Exceptions Module

This module defines a complete hierarchy of custom exceptions for the SmartPool system,
enabling granular error handling and improved observability.
"""

import time
from typing import Any, Dict, Optional

# =============================================================================
# Base Exception
# =============================================================================


class SmartPoolError(Exception):
    """
    Base exception for all SmartPool errors.

    Provides rich context for debugging and monitoring.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.cause = cause
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the exception for logging/monitoring."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp,
            "cause": str(self.cause) if self.cause else None,
        }

    def __str__(self) -> str:
        base_msg = self.message
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            base_msg += f" [{context_str}]"
        if self.cause:
            base_msg += f" (caused by: {self.cause})"
        return base_msg
