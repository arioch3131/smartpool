"""
SmartPool Custom Exceptions Module

This module defines a complete hierarchy of custom exceptions for the SmartPool system,
enabling granular error handling and improved observability.
"""

import tempfile

from smartpool.core.exceptions.base_error import SmartPoolError

# =============================================================================
# Resource Errors
# =============================================================================


class PoolResourceError(SmartPoolError):
    """Errors related to system resources."""


class MemoryLimitExceededError(PoolResourceError):
    """Memory limit exceeded."""

    def __init__(self, current_usage: int, limit: int, component: str = "pool"):
        usage_mb = current_usage / (1024 * 1024)
        limit_mb = limit / (1024 * 1024)
        usage_percent = 0.0
        if limit > 0:
            usage_percent = round((current_usage / limit * 100), 2)
        context = {
            "current_usage_bytes": current_usage,
            "limit_bytes": limit,
            "current_usage_mb": round(usage_mb, 2),
            "limit_mb": round(limit_mb, 2),
            "usage_percent": usage_percent,
            "component": component,
        }
        super().__init__(
            f"Memory limit exceeded for {component}: {usage_mb:.1f}MB/{limit_mb:.1f}MB",
            context=context,
        )


class ThreadPoolExhaustedError(PoolResourceError):
    """Thread pool exhausted."""

    def __init__(self, active_threads: int, max_threads: int, waiting_tasks: int = 0):
        utilization_percent = 0.0
        if max_threads > 0:
            utilization_percent = round((active_threads / max_threads * 100), 2)
        context = {
            "active_threads": active_threads,
            "max_threads": max_threads,
            "waiting_tasks": waiting_tasks,
            "utilization_percent": utilization_percent,
        }
        super().__init__(
            f"Thread pool exhausted: {active_threads}/{max_threads}"
            f" active threads, {waiting_tasks} waiting tasks",
            context=context,
        )


class ResourceLeakDetectedError(PoolResourceError):
    """Resource leak detected."""

    def __init__(
        self,
        resource_type: str,
        leaked_count: int,
        expected_count: int = 0,
        detection_method: str = "automatic",
    ):
        context = {
            "resource_type": resource_type,
            "leaked_count": leaked_count,
            "expected_count": expected_count,
            "detection_method": detection_method,
            "leak_ratio": leaked_count / max(1, expected_count),
        }
        super().__init__(
            f"Resource leak detected for {resource_type}: {leaked_count}"
            f" unreleased resources (expected: {expected_count})",
            context=context,
        )


class DiskSpaceExhaustedError(PoolResourceError):
    """Insufficient disk space."""

    def __init__(self, available_bytes: int, required_bytes: int, path: str = ""):
        if not path:
            path = tempfile.gettempdir()
        available_mb = available_bytes / (1024 * 1024)
        required_mb = required_bytes / (1024 * 1024)
        context = {
            "available_bytes": available_bytes,
            "required_bytes": required_bytes,
            "available_mb": round(available_mb, 2),
            "required_mb": round(required_mb, 2),
            "path": path,
        }
        super().__init__(
            f"Insufficient disk space on {path}: {available_mb:.1f}MB"
            f" available, {required_mb:.1f}MB required",
            context=context,
        )
