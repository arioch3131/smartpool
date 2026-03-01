"""
SmartPool Custom Exceptions Module

This module defines a complete hierarchy of custom exceptions for the SmartPool system,
enabling granular error handling and improved observability.
"""

import time
from collections import defaultdict
from typing import Any, Dict, List, Tuple, Type

from smartpool.core.exceptions.base_error import SmartPoolError
from smartpool.core.exceptions.factory_error import FactoryValidationError
from smartpool.core.exceptions.performance_error import HighLatencyError, LowHitRateError

from .operation_error import ObjectCorruptionError, ObjectResetFailedError

# =============================================================================
# Exception Management Utilities
# =============================================================================


class ExceptionPolicy:
    """Policy to control exception behavior."""

    def __init__(self) -> None:
        self.strict_mode = False  # Strict mode for dev/test
        self.log_all_exceptions = True
        self.raise_on_corruption = False  # Configurable by environment
        self.max_error_details = 1000  # Limit context size
        self.performance_monitoring = True

        # Recoverable exceptions in production mode
        self.recoverable_errors = {
            FactoryValidationError,
            ObjectCorruptionError,
            ObjectResetFailedError,
            HighLatencyError,
            LowHitRateError,
        }

    def should_raise(self, exception_type: Type[SmartPoolError]) -> bool:
        """Determines if an exception should be raised or just logged."""
        if self.strict_mode:
            return True

        # In production, don't raise for certain recoverable errors
        return exception_type not in self.recoverable_errors

    def should_log(self) -> bool:
        """Determines if an exception should be logged."""
        return self.log_all_exceptions

    def truncate_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Truncates context if too large."""
        serialized = str(context)
        if len(serialized) <= self.max_error_details:
            return context

        # Keep the most important keys
        important_keys = ["pool_key", "factory_class", "error_type", "operation"]
        truncated = {k: v for k, v in context.items() if k in important_keys}
        truncated["_truncated"] = True
        truncated["_original_size"] = len(serialized)
        return truncated


class ExceptionMetrics:
    """Exception metrics collection."""

    def __init__(self) -> None:
        self.exception_counters: Dict[str, int] = defaultdict(int)
        self.exception_patterns: Dict[Tuple[str, str], List[float]] = defaultdict(list)
        self.error_rates: Dict[str, List[float]] = defaultdict(list)
        self.last_cleanup = time.time()

    def record_exception(self, exception: SmartPoolError) -> None:
        """Records an exception for monitoring."""
        self.exception_counters[exception.error_code] += 1

        # Pattern detection
        pattern_key = (exception.error_code, exception.context.get("pool_key", "unknown"))
        self.exception_patterns[pattern_key].append(exception.timestamp)

        # Update error rate
        self.error_rates[exception.error_code].append(exception.timestamp)

        # Periodic cleanup (every hour)
        if time.time() - self.last_cleanup > 3600:
            self._cleanup_old_data()

    def _cleanup_old_data(self, retention_hours: int = 24) -> None:
        """Cleans up old data."""
        cutoff = time.time() - (retention_hours * 3600)

        for pattern_key in list(self.exception_patterns.keys()):
            self.exception_patterns[pattern_key] = [
                t for t in self.exception_patterns[pattern_key] if t > cutoff
            ]
            if not self.exception_patterns[pattern_key]:
                del self.exception_patterns[pattern_key]

        self.last_cleanup = time.time()

    def get_error_rate(self, error_code: str, window_seconds: int = 300) -> float:
        """Calculates error rate for an error code."""
        cutoff = time.time() - window_seconds
        count = 0

        for pattern_key, timestamps in self.exception_patterns.items():
            if pattern_key[0] == error_code:
                count += sum(1 for t in timestamps if t > cutoff)

        return count / window_seconds if window_seconds > 0 else 0

    def get_top_errors(self, limit: int = 10) -> List[tuple]:
        """Returns the most frequent errors."""
        return sorted(self.exception_counters.items(), key=lambda x: x[1], reverse=True)[:limit]

    def detect_error_spikes(self, threshold_multiplier: float = 3.0) -> List[str]:
        """Detects abnormal error spikes."""
        spikes = []

        for error_code in self.exception_counters:
            recent_rate = self.get_error_rate(error_code, 300)  # 5 minutes
            baseline_rate = self.get_error_rate(error_code, 3600)  # 1 hour

            if recent_rate > baseline_rate * threshold_multiplier:
                spikes.append(error_code)

        return spikes
