"""
SmartPool Custom Exceptions Module

This module defines a complete hierarchy of custom exceptions for the SmartPool system,
enabling granular error handling and improved observability.
"""

from typing import Optional

from smartpool.core.exceptions.base_error import SmartPoolError

# =============================================================================
# Performance Errors
# =============================================================================


class PoolPerformanceError(SmartPoolError):
    """Errors related to pool performance."""


class HighLatencyError(PoolPerformanceError):
    """High latency detected."""

    def __init__(
        self,
        operation: str,
        actual_latency_ms: float,
        threshold_ms: float,
        pool_key: Optional[str] = None,
    ):
        context = {
            "operation": operation,
            "actual_latency_ms": actual_latency_ms,
            "threshold_ms": threshold_ms,
            "latency_ratio": actual_latency_ms / threshold_ms,
            "pool_key": pool_key,
        }
        super().__init__(
            f"High latency for {operation}: {actual_latency_ms:.2f}ms"
            f" (threshold: {threshold_ms:.2f}ms)",
            context=context,
        )


# pylint: disable=too-many-arguments,too-many-positional-arguments
class LowHitRateError(PoolPerformanceError):
    """Low hit rate detected."""

    def __init__(
        self,
        hit_rate: float,
        threshold: float,
        hits: int,
        misses: int,
        pool_key: Optional[str] = None,
    ):
        context = {
            "hit_rate": hit_rate,
            "threshold": threshold,
            "hits": hits,
            "misses": misses,
            "total_requests": hits + misses,
            "pool_key": pool_key,
        }
        super().__init__(
            f"Low hit rate: {hit_rate:.1%} (threshold: {threshold:.1%})"
            f" for {hits + misses} requests",
            context=context,
        )


class ExcessiveObjectCreationError(PoolPerformanceError):
    """Excessive object creation detected."""

    def __init__(
        self,
        creation_rate: float,
        threshold_rate: float,
        time_window_seconds: int = 60,
        pool_key: Optional[str] = None,
    ):
        context = {
            "creation_rate_per_second": creation_rate,
            "threshold_rate_per_second": threshold_rate,
            "time_window_seconds": time_window_seconds,
            "pool_key": pool_key,
            "rate_ratio": creation_rate / threshold_rate,
        }
        super().__init__(
            f"Excessive object creation: {creation_rate:.1f}/s (threshold: {threshold_rate:.1f}/s)",
            context=context,
        )
