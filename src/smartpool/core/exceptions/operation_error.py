"""
SmartPool Custom Exceptions Module

This module defines a complete hierarchy of custom exceptions for the SmartPool system,
enabling granular error handling and improved observability.
"""

from typing import Dict, Optional

from .base_error import SmartPoolError

# =============================================================================
# Pool Operation Errors
# =============================================================================


class PoolOperationError(SmartPoolError):
    """Errors during pool operations."""


class ObjectAcquisitionError(PoolOperationError):
    """Errors during object acquisition."""

    def __init__(
        self,
        message: str,
        pool_key: Optional[str] = None,
        cause: Optional[Exception] = None,
        context: Optional[Dict] = None,
    ):
        _context = context.copy() if context else {}
        _context.update({"pool_key": pool_key})
        super().__init__(message, context=_context, cause=cause)
        self.pool_key = pool_key


# pylint: disable=too-many-arguments,too-many-positional-arguments
class PoolExhaustedError(ObjectAcquisitionError):
    """Pool exhausted - no objects available."""

    def __init__(
        self,
        pool_key: str,
        current_size: int,
        max_objects_per_key: int,
        active_objects_count: int = 0,
        cause: Optional[Exception] = None,
    ):
        utilization = (current_size / max_objects_per_key * 100) if max_objects_per_key > 0 else 100
        message = (
            f"Pool exhausted for key '{pool_key}' "
            f"({current_size}/{max_objects_per_key} objects, {utilization:.1f}% utilization)"
        )
        context = {
            "current_size": current_size,
            "max_objects_per_key": max_objects_per_key,
            "active_objects_count": active_objects_count,
            "utilization_percent": round(utilization, 2),
        }
        super().__init__(message, pool_key=pool_key, cause=cause, context=context)


class AcquisitionTimeoutError(ObjectAcquisitionError):
    """Timeout during acquisition."""

    def __init__(
        self,
        timeout_seconds: float,
        pool_key: Optional[str] = None,
        retry_attempts: int = 0,
        cause: Optional[Exception] = None,
    ):
        message = f"Acquisition timeout after {timeout_seconds}s for key '{pool_key or 'unknown'}'"
        context = {
            "timeout_seconds": timeout_seconds,
            "retry_attempts": retry_attempts,
        }
        super().__init__(message, pool_key=pool_key, context=context, cause=cause)


class ObjectCreationFailedError(ObjectAcquisitionError):
    """Failed to create a new object."""

    def __init__(self, pool_key: str, attempts: int = 1, cause: Optional[Exception] = None):
        message = f"Object creation failed for key '{pool_key}' after {attempts} attempt(s)"
        context = {"creation_attempts": attempts}
        super().__init__(message, pool_key=pool_key, cause=cause, context=context)


class ObjectReleaseError(PoolOperationError):
    """Errors during object release."""

    def __init__(
        self,
        message: str,
        pool_key: Optional[str] = None,
        cause: Optional[Exception] = None,
        context: Optional[Dict] = None,
    ):
        _context = context.copy() if context else {}
        _context.update({"pool_key": pool_key})
        super().__init__(message, context=_context, cause=cause)
        self.pool_key = pool_key


class ObjectValidationFailedError(ObjectReleaseError):
    """Validation failure during release."""

    def __init__(self, pool_key: str, reason: str, attempts: int = 1):
        message = f"Validation failed during release for '{pool_key}': {reason}"
        context = {
            "validation_reason": reason,
            "validation_attempts": attempts,
        }
        super().__init__(message, pool_key=pool_key, context=context)


class ObjectResetFailedError(ObjectReleaseError):
    """Reset failure during release."""

    def __init__(self, pool_key: str, cause: Optional[Exception] = None):
        message = f"Reset failed during release for '{pool_key}'"
        super().__init__(message, pool_key=pool_key, cause=cause)


# pylint: disable=too-many-arguments,too-many-positional-arguments
class ObjectCorruptionError(PoolOperationError):
    """Object corruption detected."""

    def __init__(
        self,
        pool_key: str,
        corruption_count: int,
        threshold: int,
        corruption_type: str = "validation_failure",
        cause: Optional[Exception] = None,
    ):
        context = {
            "pool_key": pool_key,
            "corruption_count": corruption_count,
            "threshold": threshold,
            "corruption_type": corruption_type,
            "threshold_exceeded": corruption_count >= threshold,
        }
        super().__init__(
            f"Corruption {corruption_type} detected for"
            f" '{pool_key}' ({corruption_count}/{threshold})",
            context=context,
            cause=cause,
        )
        self.pool_key = pool_key


class CorruptionThresholdExceededError(ObjectCorruptionError):
    """Corruption threshold exceeded for a key."""

    def __init__(self, pool_key: str, corruption_count: int, threshold: int):
        super().__init__(pool_key, corruption_count, threshold, "threshold_exceeded")
        self.message = (
            f"Corruption threshold exceeded for '{pool_key}' ({corruption_count}/{threshold})"
        )
        self.pool_key = pool_key


class ObjectStateCorruptedError(ObjectCorruptionError):
    """Corrupted object state detected."""

    def __init__(
        self, pool_key: str, object_id: Optional[str] = None, state_info: Optional[Dict] = None
    ):
        context = {"pool_key": pool_key, "object_id": object_id, "state_info": state_info or {}}
        super().__init__(pool_key, 1, 1, "state_corruption")
        self.context.update(context)
        self.message = (
            f"Corrupted state detected for object '{object_id or 'unknown'}' in pool '{pool_key}'"
        )
        self.pool_key = pool_key
