"""
Factory implementation for creating and managing Metadata buffer objects.

This module provides a MetadataFactory class that implements the ObjectFactory
interface for pooling in-memory metadata buffers, reducing allocation overhead.
"""

import os
import sys
import time
from typing import Any, Dict, List, Tuple, Union

from smartpool import ObjectFactory


class MetadataDict(dict):
    """
    Wrapper for metadata dictionaries that supports weak references.

    This class inherits from dict to have all the functionality of a dictionary,
    but as a custom class, it can be used with weakref.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Additional attributes for debugging if necessary
        self._created_at: Union[float, None] = None
        self._file_path: Union[str, None] = None

    def set_metadata(self, file_path: Union[str, None] = None) -> None:
        """Sets the wrapper's metadata."""
        self._created_at = time.time()
        self._file_path = file_path

    def __repr__(self) -> str:
        return f"MetadataDict({super().__repr__()})"


class MetadataFactory(ObjectFactory[MetadataDict]):
    """
    An implementation of `ObjectFactory` for creating and managing metadata dictionaries.
    This factory is specifically designed for use with the metadata caching system,
    where each file's metadata is stored as a MetadataDict (which supports weak references).
    """

    def create(self, *args: Any, **kwargs: Any) -> MetadataDict:
        """
        Creates a new empty MetadataDict to hold metadata for a file.

        Args:
            *args: Positional arguments (first arg expected to be file_path).
            **kwargs: Additional keyword arguments. Can include 'file_path' key.

        Returns:
            MetadataDict: A new empty MetadataDict ready to store metadata.
        """
        # Extract file_path from args or kwargs
        file_path = None
        if args:
            file_path = args[0]
        elif "file_path" in kwargs:
            file_path = kwargs.get("file_path")

        metadata_dict = MetadataDict()
        if file_path:
            metadata_dict.set_metadata(file_path)
        return metadata_dict

    def reset(self, obj: MetadataDict) -> bool:
        """
        Resets a metadata dictionary. For metadata caching, we DON'T want to clear
        the data since we want it to persist in the cache. We only reset if the
        data is corrupted or invalid.

        Args:
            obj (MetadataDict): The metadata dictionary to reset.

        Returns:
            bool: True if the dictionary is in a valid state for reuse, False otherwise.
        """
        try:
            len(obj)  # Test basic dict operations
            return True
        except (TypeError, AttributeError):
            return False

    def validate(self, obj: MetadataDict) -> bool:
        """
        Validates a metadata object to ensure it is a MetadataDict and in a usable state.

        Args:
            obj (MetadataDict): The metadata dictionary to validate.

        Returns:
            bool: True if the object is a valid MetadataDict, False otherwise.
        """

        # Additional validation: check if the dictionary isn't corrupted
        try:
            # Try to access the dictionary's methods to ensure it's not corrupted
            len(obj)
            return True
        except (TypeError, AttributeError):
            return False

    def get_key(self, *args: Any, **kwargs: Any) -> str:
        """
        Generates a unique key for metadata objects based on the file path.
        The key is normalized to ensure consistent caching across different
        representations of the same file path.

        Args:
            *args: Positional arguments (first arg expected to be file_path).
            **kwargs: Additional keyword arguments. Can include 'file_path' key.

        Returns:
            str: A normalized unique string key based on the file path.
        """
        # Extract file_path from args or kwargs
        file_path = None
        if args:
            file_path = args[0]
        else:
            file_path = kwargs.get("file_path")

        if not file_path or not isinstance(file_path, str):
            return "invalid_path"

        # Normalize the path to ensure consistent keys
        # Convert to absolute path and normalize separators
        try:
            normalized_path = os.path.abspath(os.path.normpath(file_path))
            key = f"metadata:{normalized_path}"
            return key
        except (OSError, TypeError, ValueError):
            # Fallback to raw path if normalization fails
            key = f"metadata:{file_path}"
            return key

    def destroy(self, obj: Dict[str, Any]) -> None:
        """
        Cleans up a metadata dictionary before it is permanently destroyed.
        This is called when the object is being removed from the pool entirely.

        Args:
            obj (Dict[str, Any]): The metadata dictionary to destroy.
        """
        try:
            obj.clear()
        except AttributeError:
            # If clearing fails, there's not much more we can do
            pass

    def force_clear(self, obj: Dict[str, Any]) -> bool:
        """
        Forces a clear of the metadata dictionary. This is used when we
        explicitly want to invalidate cached data.

        Args:
            obj (Dict[str, Any]): The metadata dictionary to clear.

        Returns:
            bool: True if the dictionary was successfully cleared, False otherwise.
        """
        try:
            obj.clear()
            return True
        except AttributeError:
            return False

    def estimate_size(self, obj: Dict[str, Any]) -> int:
        """
        Estimates the memory size of the metadata dictionary.
        This provides a more accurate estimation than the default sys.getsizeof()
        by considering the content of the dictionary.

        Args:
            obj (Dict[str, Any]): The metadata dictionary.

        Returns:
            int: The estimated size in bytes.
        """
        if not obj:
            return sys.getsizeof({})

        try:
            # Start with the base dictionary overhead
            total_size = sys.getsizeof(obj)

            # Add size estimates for keys and values
            for key, value in obj.items():
                total_size += sys.getsizeof(key)
                total_size += self._estimate_value_size(value)

            return total_size
        except (TypeError, AttributeError):
            # Fallback to basic estimation if detailed calculation fails
            return sys.getsizeof(obj)

    def _estimate_value_dict_size(self, value: Dict) -> int:
        """
        Estimates the size of a dict value in the metadata dictionary.
        Handles nested structures and common metadata types.

        Args:
            value (Dict): The value to estimate.

        Returns:
            int: The estimated size in bytes.
        """
        # Recursively estimate nested dictionaries
        size = sys.getsizeof(value)
        for k, v in value.items():
            size += sys.getsizeof(k) + self._estimate_value_size(v)
        return size

    def _estimate_value_list_tuple_size(self, value: Union[List[Any], Tuple[Any]]) -> int:
        """
        Estimates the size of a list or tuple value
        in the metadata dictionary. Handles nested structures and
        common metadata types.

        Args:
            value (List): The value to estimate.

        Returns:
            int: The estimated size in bytes.
        """
        # Estimate list/tuple sizes
        size = sys.getsizeof(value)
        for item in value:
            size += self._estimate_value_size(item)
        return size

    def _estimate_value_size(self, value: Any) -> int:
        """
        Estimates the size of a value in the metadata dictionary.
        Handles nested structures and common metadata types.

        Args:
            value (Any): The value to estimate.

        Returns:
            int: The estimated size in bytes.
        """
        try:
            if isinstance(value, dict):
                return self._estimate_value_dict_size(value)
            if isinstance(value, (list, tuple)):
                return self._estimate_value_list_tuple_size(value)
            # For basic types, use sys.getsizeof
            return sys.getsizeof(value)
        except (TypeError, AttributeError, RecursionError):
            # Fallback for any problematic values
            return 100  # Conservative estimate
