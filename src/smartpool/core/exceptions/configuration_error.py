"""
SmartPool Custom Exceptions Module

This module defines a complete hierarchy of custom exceptions for the SmartPool system,
enabling granular error handling and improved observability.
"""

from typing import Any, Dict, List, Optional, Union

from .base_error import SmartPoolError

# =============================================================================
# Configuration Errors
# =============================================================================


class PoolConfigurationError(SmartPoolError):
    """Errors related to pool configuration."""


class InvalidPoolSizeError(PoolConfigurationError):
    """Invalid pool size."""

    def __init__(
        self,
        provided_size: Union[int, float],
        min_size: int = 1,
        max_objects_per_key: Optional[int] = None,
    ):
        max_str = str(max_objects_per_key) if max_objects_per_key is not None else "∞"
        context = {
            "provided_size": provided_size,
            "min_size": min_size,
            "max_objects_per_key": max_objects_per_key,
        }
        super().__init__(
            f"Pool size {provided_size} invalid (must be between {min_size} and {max_str})",
            context=context,
        )


class InvalidTTLError(PoolConfigurationError):
    """Invalid TTL."""

    def __init__(self, provided_ttl: Union[float, int, str]):
        super().__init__(
            f"TTL '{provided_ttl}' invalid (must be a number > 0)",
            context={"provided_ttl": provided_ttl, "type": type(provided_ttl).__name__},
        )


class InvalidPresetError(PoolConfigurationError):
    """Invalid configuration preset."""

    def __init__(self, provided_preset: str, available_presets: List[str]):
        super().__init__(
            f"Preset '{provided_preset}' invalid. Available: {', '.join(available_presets)}",
            context={"provided_preset": provided_preset, "available_presets": available_presets},
        )


class ConfigurationConflictError(PoolConfigurationError):
    """Conflict in pool configuration."""

    def __init__(self, conflicting_params: Dict[str, Any], reason: str):
        super().__init__(
            f"Configuration conflict: {reason}",
            context={"conflicting_params": conflicting_params, "reason": reason},
        )
