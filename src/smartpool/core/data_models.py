"""
Data models for the AI content classifier memory management system.

This module defines the core data structures used by the memory pool implementation
to manage object lifecycle, metadata tracking, and resource optimization.

The primary purpose of this module is to provide a standardized way to wrap
objects with essential metadata that enables efficient pool management, including:
- Object lifecycle tracking (creation, access patterns)
- State management and validation
- Memory usage monitoring and optimization
- Performance analytics and debugging

Classes:
    PooledObject: A dataclass wrapper that associates objects with their
        management metadata within the memory pool system.

Dependencies:
    - dataclasses: For creating structured data classes
    - typing: For type annotations and hints
    - ai_content_classifier.core.memory.factories.factory_interface: For ObjectState enum

Note:
    This module is part of the ai_content_classifier memory management system
    and should be used in conjunction with the pool implementations that
    properly maintain the metadata fields during object lifecycle operations.
"""

from dataclasses import dataclass
from typing import Any

from smartpool.core.factory_interface import ObjectState


@dataclass
class PooledObject:
    """
    A wrapper dataclass for objects stored in the memory pool with metadata.

    This class serves as a container for objects managed by a memory pool system,
    providing essential metadata for lifecycle management, performance tracking,
    and resource optimization.

    The metadata enables efficient pool management by tracking object usage patterns,
    detecting corruption, monitoring memory consumption, and maintaining object state
    throughout its lifecycle in the pool.

    Attributes:
        obj (Any): The actual object instance being pooled. This can be any type
            of object that the pool is designed to manage.
        created_at (float): Unix timestamp indicating when this pooled object
            wrapper was created and the object was first added to the pool.
        last_accessed (float): Unix timestamp of the most recent time this
            object was acquired from the pool for use.
        access_count (int): Total number of times this object has been
            successfully acquired from the pool. Defaults to 0.
        validation_failures (int): Counter tracking consecutive validation
            failures. Used to identify potentially corrupted or problematic
            objects that should be removed from the pool. Defaults to 0.
        state (ObjectState): Current lifecycle state of the object within
            the pool system (e.g., VALID, IN_USE, CORRUPTED).
            Defaults to ObjectState.VALID.
        estimated_size (int): Approximate memory footprint of the object
            in bytes. Used for memory usage tracking, pool size limits,
            and optimization decisions. Defaults to 0.

    Note:
        This is a dataclass, so all standard dataclass functionality
        (equality comparison, string representation, etc.) is available.
        The object should be managed by a pool implementation that
        properly updates the metadata fields during the object lifecycle.
    """

    obj: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    validation_failures: int = 0
    state: ObjectState = ObjectState.VALID
    estimated_size: int = 0
