"""
SmartPool Custom Exceptions Module

This module defines a complete hierarchy of custom exceptions for the SmartPool system,
enabling granular error handling and improved observability.
"""

from typing import Any, Optional

from smartpool.core.exceptions.factory_error import (
    FactoryCreationError,
    FactoryDestroyError,
    FactoryError,
    FactoryKeyGenerationError,
    FactoryResetError,
    FactoryValidationError,
)

from .operation_error import (
    AcquisitionTimeoutError,
    ObjectAcquisitionError,
    ObjectCorruptionError,
    ObjectCreationFailedError,
    ObjectReleaseError,
    ObjectResetFailedError,
    ObjectValidationFailedError,
    PoolExhaustedError,
    PoolOperationError,
)

# =============================================================================
# Factory for Creating Exceptions with Context
# =============================================================================


class SmartPoolExceptionFactory:
    """Factory to create exceptions with standardized context."""

    @staticmethod
    def create_factory_error(
        error_type: str,
        factory_class: str,
        method_name: str,
        message: Optional[str] = None,  # Added message
        cause: Optional[Exception] = None,
        **context_kwargs: Any,
    ) -> FactoryError:
        """Creates a factory exception with standardized context."""

        if error_type == "creation":
            return FactoryCreationError(
                factory_class=factory_class,
                args=context_kwargs.get("args"),
                kwargs_dict=context_kwargs.get("kwargs"),
                cause=cause,
            )
        if error_type == "validation":
            return FactoryValidationError(
                factory_class=factory_class,
                validation_attempts=context_kwargs.get("attempts", 0),
                max_attempts=context_kwargs.get("max_attempts", 1),
                cause=cause,
            )
        if error_type == "reset":
            return FactoryResetError(
                factory_class=factory_class,
                object_type=context_kwargs.get("object_type"),
                cause=cause,
            )
        if error_type == "destroy":
            return FactoryDestroyError(
                factory_class=factory_class,
                object_type=context_kwargs.get("object_type"),
                cause=cause,
            )
        if error_type == "key_generation":
            return FactoryKeyGenerationError(
                factory_class=factory_class,
                args=context_kwargs.get("args"),
                kwargs_dict=context_kwargs.get("kwargs"),
                cause=cause,
            )
        # Fallback to generic FactoryError
        return FactoryError(
            message or f"Generic factory error for type {error_type}",
            factory_class=factory_class,
            method_name=method_name,
            cause=cause,
            context=context_kwargs,  # Pass context_kwargs as the context
        )

    # pylint: disable=too-many-return-statements
    @staticmethod
    def create_pool_operation_error(  # noqa: PLR0911
        error_type: str, pool_key: str, cause: Optional[Exception] = None, **context_kwargs: Any
    ) -> PoolOperationError:
        """Create a pool operation error."""

        if error_type == "exhausted":
            return PoolExhaustedError(
                pool_key=pool_key,
                current_size=context_kwargs.get("current_size", 0),
                max_objects_per_key=context_kwargs.get("max_size", 0),
                active_objects_count=context_kwargs.get("active_objects_count", 0),
                cause=cause,
            )
        if error_type == "timeout":
            return AcquisitionTimeoutError(
                timeout_seconds=context_kwargs.get("timeout_seconds", 0),
                pool_key=pool_key,
                retry_attempts=context_kwargs.get("retry_attempts", 0),
                cause=cause,
            )
        if error_type == "creation_failed":
            return ObjectCreationFailedError(
                pool_key=pool_key, attempts=context_kwargs.get("attempts", 1), cause=cause
            )
        if error_type == "reset":
            return ObjectResetFailedError(pool_key=pool_key, cause=cause)
        if error_type == "validation":
            return ObjectValidationFailedError(
                pool_key=pool_key,
                reason=context_kwargs.get("reason", ""),
                attempts=context_kwargs.get("attempts", 1),
            )
        if error_type == "corruption":
            return ObjectCorruptionError(
                pool_key=pool_key,
                corruption_count=context_kwargs.get("corruption_count", 1),
                threshold=context_kwargs.get("threshold", 1),
                corruption_type=context_kwargs.get("corruption_type", "unknown"),
                cause=cause,
            )
        if error_type == "acquisition_failed":
            return ObjectAcquisitionError(
                message=f"Acquisition failed for pool '{pool_key}'", pool_key=pool_key, cause=cause
            )
        if error_type == "release_failed":
            return ObjectReleaseError(
                message=f"Release failed for pool '{pool_key}'", pool_key=pool_key, cause=cause
            )
        # Fallback to generic PoolOperationError
        return PoolOperationError(
            f"Operation error {error_type} for pool '{pool_key}'", cause=cause
        )
