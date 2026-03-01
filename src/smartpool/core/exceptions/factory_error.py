"""
SmartPool Custom Exceptions Module

This module defines a complete hierarchy of custom exceptions for the SmartPool system,
enabling granular error handling and improved observability.
"""

from typing import Any, Optional

from .base_error import SmartPoolError

# =============================================================================
# Factory Errors
# =============================================================================


class FactoryError(SmartPoolError):
    """Errors related to factory operations."""

    def __init__(
        self,
        message: str,
        factory_class: Optional[str] = None,
        method_name: Optional[str] = None,
        **kwargs: Any,
    ):
        context = kwargs.get("context", {})
        context.update({"factory_class": factory_class, "method_name": method_name})
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class FactoryCreationError(FactoryError):
    """Object creation failure by factory."""

    def __init__(
        self,
        factory_class: str,
        args: Optional[tuple] = None,
        kwargs_dict: Optional[dict] = None,
        cause: Optional[Exception] = None,
    ):
        context = {
            "args": args,
            "kwargs": kwargs_dict,
            "args_count": len(args) if args else 0,
            "kwargs_count": len(kwargs_dict) if kwargs_dict else 0,
        }
        super().__init__(
            f"Object creation failed with factory {factory_class}",
            factory_class=factory_class,
            method_name="create",
            context=context,
            cause=cause,
        )


class FactoryValidationError(FactoryError):
    """Object validation failure."""

    def __init__(
        self,
        factory_class: str,
        validation_attempts: int = 0,
        max_attempts: int = 1,
        cause: Optional[Exception] = None,
    ):
        context = {
            "validation_attempts": validation_attempts,
            "max_attempts": max_attempts,
            "attempts_exhausted": validation_attempts >= max_attempts,
        }
        super().__init__(
            f"Validation failed after {validation_attempts}/{max_attempts} attempts",
            factory_class=factory_class,
            method_name="validate",
            context=context,
            cause=cause,
        )


class FactoryResetError(FactoryError):
    """Object reset failure."""

    def __init__(
        self,
        factory_class: str,
        object_type: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        context = {"object_type": object_type}
        super().__init__(
            f"Object reset failed for {object_type or 'unknown'} with factory {factory_class}",
            factory_class=factory_class,
            method_name="reset",
            context=context,
            cause=cause,
        )


class FactoryDestroyError(FactoryError):
    """Object destruction failure."""

    def __init__(
        self,
        factory_class: str,
        object_type: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        context = {"object_type": object_type}
        super().__init__(
            f"Object destruction failed for {object_type or 'unknown'}"
            f" with factory {factory_class}",
            factory_class=factory_class,
            method_name="destroy",
            context=context,
            cause=cause,
        )


class FactoryKeyGenerationError(FactoryError):
    """Key generation failure by factory."""

    def __init__(
        self,
        factory_class: str,
        args: Optional[tuple] = None,
        kwargs_dict: Optional[dict] = None,
        cause: Optional[Exception] = None,
    ):
        context = {"args": args, "kwargs": kwargs_dict}
        super().__init__(
            f"Key generation failed with factory {factory_class}",
            factory_class=factory_class,
            method_name="get_key",
            context=context,
            cause=cause,
        )
