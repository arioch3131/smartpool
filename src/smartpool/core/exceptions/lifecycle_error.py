"""
SmartPool Custom Exceptions Module

This module defines a complete hierarchy of custom exceptions for the SmartPool system,
enabling granular error handling and improved observability.
"""

import time
from typing import Optional

from smartpool.core.exceptions.base_error import SmartPoolError

# =============================================================================
# Lifecycle Errors
# =============================================================================


class PoolLifecycleError(SmartPoolError):
    """Errors related to pool lifecycle."""


class PoolAlreadyShutdownError(PoolLifecycleError):
    """Attempt to use a closed pool."""

    def __init__(self, operation: str, shutdown_time: Optional[float] = None):
        context = {
            "attempted_operation": operation,
            "shutdown_time": shutdown_time,
            "time_since_shutdown": time.time() - shutdown_time if shutdown_time else None,
        }
        super().__init__(f"Cannot execute '{operation}': pool is shutdown", context=context)


class PoolInitializationError(PoolLifecycleError):
    """Pool initialization failure."""

    def __init__(self, component: str, stage: str = "unknown", cause: Optional[Exception] = None):
        context = {"failed_component": component, "initialization_stage": stage}
        super().__init__(
            f"Initialization failed for component '{component}' during stage '{stage}'",
            context=context,
            cause=cause,
        )


class BackgroundManagerError(PoolLifecycleError):
    """Background task manager errors."""

    def __init__(
        self, task_name: str, error_type: str = "execution", cause: Optional[Exception] = None
    ):
        context = {
            "task_name": task_name,
            "error_type": error_type,  # 'execution', 'scheduling', 'shutdown'
        }
        super().__init__(
            f"Error {error_type} in background task '{task_name}'", context=context, cause=cause
        )


class ManagerSynchronizationError(PoolLifecycleError):
    """Synchronization error between managers."""

    def __init__(
        self, manager1: str, manager2: str, operation: str, cause: Optional[Exception] = None
    ):
        context = {"manager1": manager1, "manager2": manager2, "operation": operation}
        super().__init__(
            f"Synchronization error between {manager1} and {manager2} during '{operation}'",
            context=context,
            cause=cause,
        )
