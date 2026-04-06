"""
Pool Operations Manager Module.

This module provides the PoolOperationsManager class which handles complex,
low-level operations within memory pools including object validation, expiration,
corruption handling, and LRU eviction strategies.
"""

import logging
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Deque, Dict, Optional

from smartpool.core.data_models import ObjectState, PooledObject
from smartpool.core.exceptions import SmartPoolExceptionFactory
from smartpool.core.utils import safe_log

if TYPE_CHECKING:  # pragma: no cover
    from smartpool.core.smartpool_manager import (
        MemoryConfig,
        SmartObjectManager,
    )


@dataclass
class PoolOperationResult:
    """
    Represents the result of an object retrieval operation from the pool.
    This dataclass encapsulates whether the operation was successful, the object found (if any),
    and any error messages.

    Attributes:
        success (bool): True if the operation was successful (an object was found or created),
                        False otherwise.
        object_found (Optional['PooledObject']): The `PooledObject` instance
                                                if an object was successfully
                                                retrieved from the pool. None otherwise.
        error_message (Optional[str]): A descriptive error message
                                    if the operation failed. None on success.
        objects_processed (int): The number of objects processed
                                (e.g., validated, expired) during the search.
    """

    success: bool
    object_found: Optional["PooledObject"] = None
    error_message: Optional[str] = None
    objects_processed: int = 0


class PoolOperationsManager:
    """
    Manages complex, low-level operations within the memory pool, such as object validation,
    expiration, corruption handling, and LRU (Least Recently Used) eviction strategies.
    This manager directly interacts with the pool's internal data structures.

    Responsibilities:
    - Searching for and validating objects within the pool's queues.
    - Implementing LRU eviction policies to manage pool size.
    - Tracking and managing corrupted objects to prevent their reuse.
    - Cleaning up expired objects from the pool.
    - Adding and removing objects from the internal pool data structures.
    """

    def __init__(self, pool: "SmartObjectManager"):
        """
        Initializes the PoolOperationsManager.

        Args:
            pool (SmartObjectManager): A reference to the main memory pool, used to access
                                      its factory, statistics, and configuration.
        """
        self.pool = pool
        self.logger = logging.getLogger(__name__)
        # Cached optional callables to reduce attribute lookups in hot paths.
        getter = getattr(pool, "get_total_pooled_objects", None)
        self._get_total_pooled_objects = getter if callable(getter) else None
        adjuster = getattr(pool, "_adjust_total_pooled_objects", None)
        self._adjust_total_pooled_objects = adjuster if callable(adjuster) else None

        # OrderedDict to track the access order of keys for LRU eviction.
        # Keys are object categories, values are their last access timestamps.
        # The order reflects recency of use.
        self._key_access_order: OrderedDict[str, float] = OrderedDict()

        # Dictionary to store counts of corrupted objects per key. Used to detect recurring issues.
        self._corrupted_objects: Dict[str, int] = {}

    def update_key_access(self, key: str, access_time: float) -> None:
        """
        Updates the access timestamp for a given key and moves it to the end of the LRU order.
        This signifies that objects associated with this key have been recently accessed.

        Args:
            key (str): The unique key of the object category being accessed.
            access_time (float): The timestamp of the access.
        """
        self._key_access_order[key] = access_time
        self._key_access_order.move_to_end(key)  # Mark as recently used

    def find_valid_object_with_retry(
        self,
        key: str,
        current_time: float,
        config: "MemoryConfig",
        pool_data: Dict[str, Deque["PooledObject"]],
    ) -> PoolOperationResult:
        """
        Attempts to find a valid, non-expired object in the pool for a given key.
        It includes retry logic for validation failures, allowing an object to be re-validated
        a certain number of times before being marked as corrupted.

        Args:
            key (str): The key of the object category to search for.
            current_time (float): The current timestamp, used to check for object expiration.
            config (MemoryConfig): The configuration for the given key,
                            including `max_validation_attempts` and `ttl_seconds`.
            pool_data (Dict[str, Deque['PooledObject']]): The internal dictionary
                            representing the pool's data structure.

        Returns:
            PoolOperationResult: An object indicating whether a valid object was found,
                                the object itself, or an error message if no valid object
                                could be retrieved after retries.
        """
        if key not in pool_data:
            return PoolOperationResult(success=False, error_message="Key not in pool")

        queue = pool_data[key]
        attempts = 0
        processed = 0

        # Iterate through the queue, attempting to find a valid object.
        while queue and attempts < config.max_validation_attempts:
            pooled_obj = queue.popleft()  # Take object from the front of the queue
            attempts += 1
            processed += 1

            # Check if the object has expired based on its creation time and TTL.
            if self._is_expired(pooled_obj, current_time, config):
                self._adjust_total_objects(-1)
                self.pool.stats.increment("expired")
                pooled_obj.state = ObjectState.EXPIRED
                self._try_destroy_object(pooled_obj.obj)  # Destroy expired object
                continue  # Try next object in queue

            # Validate the object using the factory's validation method.
            validation_result = self._validate_pooled_object(pooled_obj, key, queue, config)
            if validation_result.success:
                self._adjust_total_objects(-1)
                return PoolOperationResult(
                    success=True, object_found=pooled_obj, objects_processed=processed
                )

        # No valid object found after exhausting retries or queue.
        return PoolOperationResult(
            success=False,
            error_message="No valid object found after retries",
            objects_processed=processed,
        )

    def _is_expired(
        self, pooled_obj: "PooledObject", current_time: float, config: "MemoryConfig"
    ) -> bool:
        """
        Checks if a `PooledObject` has exceeded its time-to-live (TTL).

        Args:
            pooled_obj (PooledObject): The object to check for expiration.
            current_time (float): The current timestamp.
            config (MemoryConfig): The configuration containing the `ttl_seconds`.

        Returns:
            bool: True if the object is expired, False otherwise.
        """
        return current_time - pooled_obj.created_at > config.ttl_seconds

    def _create_fail_pool_operation_result(
        self,
        pooled_obj: "PooledObject",
        key: str,
        queue: Deque["PooledObject"],
        config: Optional["MemoryConfig"] = None,
    ) -> PoolOperationResult:
        """
        Internal method to generate a failed PoolOperationResult.

        Args:
            pooled_obj (PooledObject): The object to validate.
            key: (str): The key of the object.
            queue: (Deque['PooledObject']): The queue from which the object was taken
                                        (used for requeuing).

        Returns:
            A Failed PoolOperationResult.
        """
        # If validation fails too many times, mark as corrupted.
        effective_config = config if config is not None else self.pool.get_config_for_key(key)
        if pooled_obj.validation_failures >= effective_config.max_validation_attempts:
            self._adjust_total_objects(-1)
            self._mark_as_corrupted(key, pooled_obj)
            return PoolOperationResult(
                success=False,
                error_message="Object corrupted after multiple failures",
            )
        # Requeue for another retry if not yet corrupted.
        queue.append(pooled_obj)  # Add back to the end of the queue
        return PoolOperationResult(
            success=False,
            error_message="Validation failed, object requeued",
        )

    def _validate_pooled_object(
        self,
        pooled_obj: "PooledObject",
        key: str,
        queue: Deque["PooledObject"],
        config: Optional["MemoryConfig"] = None,
    ) -> PoolOperationResult:
        """
        Internal method to validate a `PooledObject` using the associated factory.
        Handles validation failures by incrementing a counter and potentially marking
        the object as corrupted.

        Args:
            pooled_obj (PooledObject): The object to validate.
            key (str): The key of the object.
            queue (Deque['PooledObject']): The queue from which the object was taken
                                        (used for requeuing).

        Returns:
            PoolOperationResult: Indicates validation success or failure, and if failed,
                                whether it was requeued or corrupted.
        """
        try:
            if self.pool.factory.validate(pooled_obj.obj):
                pooled_obj.validation_failures = 0  # Reset failures on success
                return PoolOperationResult(success=True)
            pooled_obj.validation_failures += 1
            self.pool.stats.increment("validation_failures")
            return self._create_fail_pool_operation_result(pooled_obj, key, queue, config)

        except (TypeError, AttributeError, ValueError, RuntimeError) as e:
            # Log and mark as corrupted if validation itself raises an exception.
            effective_config = config if config is not None else self.pool.get_config_for_key(key)
            ex = SmartPoolExceptionFactory.create_factory_error(
                error_type="validation",
                factory_class=self.pool.factory.__class__.__name__,
                method_name="validate",
                cause=e,
                validation_attempts=pooled_obj.validation_failures + 1,
                max_attempts=effective_config.max_validation_attempts,
            )
            self.pool._handle_exception(ex)  # pylint: disable=protected-access
            self._mark_as_corrupted(key, pooled_obj)
            return PoolOperationResult(success=False, error_message=f"Validation exception: {e}")

    def _mark_as_corrupted(
        self,
        key: str,
        pooled_obj: "PooledObject",
        config: Optional["MemoryConfig"] = None,
    ) -> None:
        """
        Marks a `PooledObject` as corrupted, increments corruption statistics for its key,
        and destroys the underlying object. If the corruption threshold for a key is reached,
        an error is logged.

        Args:
            key (str): The key of the corrupted object.
            pooled_obj (PooledObject): The `PooledObject` instance to mark as corrupted.
        """
        pooled_obj.state = ObjectState.CORRUPTED
        self.pool.stats.increment("corrupted")

        self._corrupted_objects[key] = self._corrupted_objects.get(key, 0) + 1

        effective_config = config if config is not None else self.pool.get_config_for_key(key)
        if self._corrupted_objects[key] >= effective_config.max_corrupted_objects:
            safe_log(
                self.logger,
                logging.ERROR,
                f"High number of corrupted objects ({self._corrupted_objects[key]}) "
                f"for key {key}. Consider investigating the factory.",
            )

        self._try_destroy_object(pooled_obj.obj)  # Destroy the corrupted object

    def should_add_to_pool(
        self, pool_data: Dict[str, Deque["PooledObject"]], max_total_objects: int
    ) -> bool:
        """
        Determines if a newly released object should be added back to the pool.
        This decision is based on the total number of objects currently in the pool
        relative to the `max_total_objects` limit. If the limit is reached, LRU eviction
        is triggered to make space.

        Args:
            pool_data (Dict[str, Deque["PooledObject"]]): The internal pool data structure.
            max_total_objects (int): The global maximum number of objects allowed in the pool.

        Returns:
            bool: True if the object can be added to the pool, False otherwise.
        """
        total_objects = self._get_total_objects(pool_data)
        if total_objects < max_total_objects:
            return True

        # If global limit reached, try to evict least recently used objects.
        evicted = self.evict_least_recently_used(pool_data)
        if evicted > 0:
            safe_log(self.logger, logging.INFO, f"LRU eviction: removed {evicted} objects")
        return (total_objects - evicted) < max_total_objects

    def evict_least_recently_used(self, pool_data: Dict[str, Deque["PooledObject"]]) -> int:
        """
        Evicts a portion of the least recently used objects from the pool to free up space.
        It iterates through keys in LRU order and removes objects from their respective queues.

        Args:
            pool_data (Dict[str, Deque['PooledObject']]): The internal pool data structure.

        Returns:
            int: The number of objects that were evicted.
        """
        if not self._key_access_order:
            return 0

        total_objects = self._get_total_objects(pool_data)
        # Determine how many objects to evict (e.g., 25% of current total, minimum 1).
        to_evict = max(1, total_objects // 4)
        evicted = 0
        keys_to_remove = []

        # Iterate from the least recently used keys to evict objects.
        for key in list(self._key_access_order.keys()):
            if evicted >= to_evict:  # Stop if enough objects have been evicted
                break

            if key in pool_data and pool_data[key]:
                queue = pool_data[key]
                # Evict a portion of objects from this key's queue (e.g., half).
                evict_count = max(1, len(queue) // 2)

                for _ in range(min(evict_count, len(queue))):
                    if queue:  # Ensure queue is not empty before popping
                        pooled_obj = queue.popleft()  # Remove from the front (oldest)
                        self._adjust_total_objects(-1)
                        self._try_destroy_object(pooled_obj.obj)
                        self.pool.stats.increment("evictions")
                        evicted += 1

                # Mark empty queues for deletion from _key_access_order and pool_data.
                if not queue:
                    keys_to_remove.append(key)

        # Clean up empty keys from tracking structures.
        for key in keys_to_remove:
            if key in pool_data:
                del pool_data[key]
            if key in self._key_access_order:
                del self._key_access_order[key]

        return evicted

    def _get_total_objects(self, pool_data: Dict[str, Deque["PooledObject"]]) -> int:
        """
        Returns total pooled objects using the pool's incremental counter when available.

        Falls back to a direct queue-length sum for mocked pools in unit tests.
        """
        getter = self._get_total_pooled_objects
        if callable(getter):
            total = getter()
            if isinstance(total, int):
                return total
        return sum(len(queue) for queue in pool_data.values())

    def _adjust_total_objects(self, delta: int) -> None:
        """Adjust pooled-object counter when the pool exposes an internal adjuster."""
        adjuster = self._adjust_total_pooled_objects
        if adjuster is not None:
            adjuster(delta)

    def cleanup_expired_objects(
        self, pool_data: Dict[str, Deque["PooledObject"]], current_time: float
    ) -> int:
        """
        Scans through all objects in the pool and removes those that have expired.
        Expired objects are destroyed to free up resources.

        Args:
            pool_data (Dict[str, Deque['PooledObject']]): The internal pool data structure.
            current_time (float): The current timestamp.

        Returns:
            int: The total number of expired objects that were removed.
        """
        expired_count = 0
        keys_to_remove = []

        for key, queue in pool_data.items():
            config = self.pool.get_config_for_key(key)
            queue_before = len(queue)
            removed_in_key = 0

            # In-place filtering to avoid allocating a new deque for every key.
            for _ in range(queue_before):
                pooled_obj = queue.popleft()
                if self._is_expired(pooled_obj, current_time, config):
                    self._try_destroy_object(pooled_obj.obj)
                    expired_count += 1
                    removed_in_key += 1
                else:
                    queue.append(pooled_obj)

            if not queue:  # If queue becomes empty, mark key for removal
                keys_to_remove.append(key)

            if removed_in_key > 0:
                self._adjust_total_objects(-removed_in_key)

        # Clean up keys that now have empty queues.
        for key in keys_to_remove:
            if key in pool_data:
                del pool_data[key]
            if key in self._key_access_order:
                del self._key_access_order[key]

        if expired_count > 0:
            self.pool.stats.increment("expired", expired_count)
            safe_log(self.logger, logging.INFO, f"Cleanup: removed {expired_count} expired objects")

        return expired_count

    def validate_and_reset_object(self, obj: Any, key: str, _: "MemoryConfig") -> bool:
        """
        Validates and resets an object before it is returned to the pool.
        This ensures the object is in a clean and usable state for future acquisitions.
        If validation or reset fails, the object is destroyed.

        Args:
            obj (Any): The object instance to validate and reset.
            key (str): The key associated with the object.

        Returns:
            bool: True if the object was successfully validated and reset, False otherwise.
        """
        # 1. Validation: Check if the object is still valid for reuse.
        try:
            if not self.pool.factory.validate(obj):
                self.pool.stats.increment("validation_failures")
                safe_log(
                    self.logger,
                    logging.WARNING,
                    f"Object validation failed for key {key}. Destroying object.",
                )
                self._try_destroy_object(obj)
                return False
        except (TypeError, AttributeError, ValueError, RuntimeError) as e:
            safe_log(
                self.logger,
                logging.WARNING,
                f"Exception during object validation for key {key}: {e}. Destroying object.",
            )
            ex = SmartPoolExceptionFactory.create_factory_error(
                error_type="validation",
                factory_class=self.pool.factory.__class__.__name__,
                method_name="validate",
                cause=e,
            )
            self.pool._handle_exception(ex)  # pylint: disable=protected-access
            self._try_destroy_object(obj)
            return False

        # 2. Reset: Reset the object to its initial state.
        try:
            if not self.pool.factory.reset(obj):
                self.pool.stats.increment("reset_failures")
                safe_log(
                    self.logger,
                    logging.WARNING,
                    f"Object reset failed for key {key}. Destroying object.",
                )
                self._try_destroy_object(obj)
                return False
        except (TypeError, AttributeError, ValueError, RuntimeError) as e:
            safe_log(
                self.logger,
                logging.WARNING,
                f"Exception during object reset for key {key}: {e}. Destroying object.",
            )
            ex = SmartPoolExceptionFactory.create_factory_error(
                error_type="reset",
                factory_class=self.pool.factory.__class__.__name__,
                method_name="reset",
                cause=e,
                object_type=type(obj).__name__,
            )
            self.pool.stats.increment("reset_failures")
            self.pool._handle_exception(ex)  # pylint: disable=protected-access
            self._try_destroy_object(obj)
            return False

        return True  # Object is valid and reset

    def add_to_pool(
        self,
        key: str,
        obj: Any,
        config: "MemoryConfig",
        pool_data: Dict[str, Deque["PooledObject"]],
        *,
        estimated_size: Optional[int] = None,
    ) -> bool:
        """
        Adds a `PooledObject` back to the pool for a specific key, provided there is space
        in that key's queue (up to `config.max_objects_per_key`).

        Args:
            key (str): The key of the object category.
            obj (Any): The raw object instance to add to the pool.
            config (MemoryConfig): The configuration for the object's key,
                                    including `max_objects_per_key`.
            pool_data (Dict[str, Deque['PooledObject']]): The internal pool data structure.

        Returns:
            bool: True if the object was successfully added to the pool, False if the pool
                  for that key was already full (in which case the object is destroyed).
        """
        created_ts = time.time()
        size_bytes = (
            estimated_size if estimated_size is not None else self.pool.factory.estimate_size(obj)
        )
        pooled_obj = PooledObject(
            obj=obj,
            created_at=created_ts,
            last_accessed=created_ts,
            state=ObjectState.VALID,
            estimated_size=size_bytes,
        )
        return self.add_pooled_object(key, pooled_obj, config, pool_data)

    def add_pooled_object(
        self,
        key: str,
        pooled_obj: "PooledObject",
        config: "MemoryConfig",
        pool_data: Dict[str, Deque["PooledObject"]],
    ) -> bool:
        """
        Adds a pre-built `PooledObject` to the pool for a key, respecting
        `max_objects_per_key`.

        This variant avoids repeated wrapping work inside lock-heavy paths.
        """
        queue = pool_data.get(key)
        if queue is None:
            queue = deque()
            pool_data[key] = queue

        if len(queue) >= config.max_objects_per_key:
            safe_log(
                self.logger,
                logging.INFO,
                (
                    "Pool for key "
                    f"{key} is full (max_objects_per_key={config.max_objects_per_key}), "
                    "destroying object."
                ),
            )
            self._try_destroy_object(pooled_obj.obj)
            return False

        queue.append(pooled_obj)
        self._adjust_total_objects(1)
        safe_log(self.logger, logging.DEBUG, f"Object returned to pool for key {key}")
        return True

    def _try_destroy_object(self, obj: Any) -> None:
        """
        Safely attempts to destroy an object using the pool's factory.
        Any exceptions during destruction are caught and
        logged to prevent crashes.

        Args:
            obj (Any): The object instance to destroy.
        """
        try:
            self.pool.factory.destroy(obj)
            self.pool.stats.increment("destroys")
        except (TypeError, AttributeError, OSError, RuntimeError) as e:
            safe_log(self.logger, logging.WARNING, f"Failed to destroy object: {e}")
            ex = SmartPoolExceptionFactory.create_factory_error(
                error_type="destroy",
                factory_class=self.pool.factory.__class__.__name__,
                method_name="destroy",
                cause=e,
                object_type=type(obj).__name__,
            )
            self.pool._handle_exception(ex)  # pylint: disable=protected-access

    def cleanup_corruption_stats(self, max_keys: int = 100) -> int:
        """
        Cleans up old corruption statistics to prevent the `_corrupted_objects` dictionary
        from growing indefinitely. It retains statistics for the most recent `max_keys`.

        Args:
            max_keys (int): The maximum number of keys for which to retain corruption statistics.

        Returns:
            int: The number of keys whose corruption statistics were removed.
        """
        if len(self._corrupted_objects) > max_keys:
            num_to_remove = len(self._corrupted_objects) - max_keys
            keys_to_remove = list(self._corrupted_objects.keys())[
                :num_to_remove
            ]  # Remove the oldest 'num_to_remove' keys
            for key in keys_to_remove:
                del self._corrupted_objects[key]
            return len(keys_to_remove)
        return 0

    def get_corruption_stats(self) -> Dict[str, int]:
        """
        Retrieves a copy of the current corruption statistics, showing the count of corrupted
        objects for each key.

        Returns:
            Dict[str, int]: A dictionary where keys are object categories and values are the
                            number of corrupted objects detected for that category.
        """
        return self._corrupted_objects.copy()

    def get_lru_stats(self) -> Dict[str, float]:
        """
        Retrieves a copy of the current LRU access order, showing the last access timestamp
        for each tracked key.

        Returns:
            Dict[str, float]: A dictionary where keys are object categories and values are their
                              last access timestamps.
        """
        return dict(self._key_access_order)

    def clear_all_data(self, pool_data: Dict[str, Deque["PooledObject"]]) -> int:
        """
        Clears all objects from the pool's internal data structures and destroys them.
        Also resets LRU and corruption statistics.

        Args:
            pool_data (Dict[str, Deque['PooledObject']]): The internal pool data structure to clear.

        Returns:
            int: The total number of objects that were destroyed.
        """
        destroyed_count = 0

        # Destroy all pooled objects.
        for queue in pool_data.values():
            for pooled_obj in queue:
                try:
                    self._try_destroy_object(pooled_obj.obj)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    # Shutdown should be best-effort: continue clearing even if one object fails.
                    safe_log(
                        self.logger,
                        logging.WARNING,
                        f"Failed to destroy object during pool clear: {exc}",
                    )
                destroyed_count += 1

        # Clear all internal tracking structures.
        pool_data.clear()
        self._key_access_order.clear()
        self._corrupted_objects.clear()

        return destroyed_count
