Core API
========

SmartPool Manager
-----------------

.. automodule:: smartpool.core.smartpool_manager
   :members:
   :undoc-members:
   :show-inheritance:

Factory Interface
-----------------

ObjectFactory
~~~~~~~~~~~~~~

.. automodule:: smartpool.core.factory_interface
   :members:
   :show-inheritance:
   :undoc-members:
   :exclude-members: ObjectState

ObjectState
~~~~~~~~~~~~

.. automodule:: smartpool.core.factory_interface.ObjectState
   :show-inheritance:
   :members:
   :undoc-members:
   :exclude-members: VALID, CORRUPTED, EXPIRED, IN_USE

Data Models
-----------

PooledObject
~~~~~~~~~~~~

.. automodule:: smartpool.core.data_models.PooledObject
   :members:
   :show-inheritance:
   :undoc-members:
   :exclude-members: obj, created_at, last_accessed, access_count, validation_failures, state, estimated_size

Managers
--------

Active Object Manager
~~~~~~~~~~~~~~~~~~~~~

ActiveObjectManager
^^^^^^^^^^^^^^^^^^^

.. automodule:: smartpool.core.managers.active_objects_manager
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: ActiveObjectInfo

ActiveObjectInfo
^^^^^^^^^^^^^^^^

.. automodule:: smartpool.core.managers.active_objects_manager.ActiveObjectInfo
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: key, estimated_size, created_at, access_count


Background Manager
~~~~~~~~~~~~~~~~~~

.. automodule:: smartpool.core.managers.background_manager
   :members:
   :undoc-members:
   :show-inheritance:

Memory Manager
~~~~~~~~~~~~~~

MemoryManager
^^^^^^^^^^^^^

.. automodule:: smartpool.core.managers.memory_manager
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: ObjectInfoPooled, ObjectInfoActive, KeyData

ObjectInfoPooled
^^^^^^^^^^^^^^^^

.. automodule:: smartpool.core.managers.memory_manager.ObjectInfoPooled
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: age_seconds, access_count, time_since_last_access, state, size_bytes

ObjectInfoActive
^^^^^^^^^^^^^^^^

.. automodule:: smartpool.core.managers.memory_manager.ObjectInfoActive
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: obj_id, age_seconds, access_count, size_bytes


KeyData
^^^^^^^

.. automodule:: smartpool.core.managers.memory_manager.KeyData
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: total_pooled_objects, active_objects_count, pooled_count, active_count, pooled_memory, active_memory


Memory Optimizer
~~~~~~~~~~~~~~~~

.. automodule:: smartpool.core.managers.memory_optimizer
   :members:
   :undoc-members:
   :show-inheritance:

Pool Operation Manager
~~~~~~~~~~~~~~~~~~~~~~

PoolOperationManager
^^^^^^^^^^^^^^^^^^^^

.. automodule:: smartpool.core.managers.pool_operations_manager
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: PoolOperationResult

PoolOperationResult
^^^^^^^^^^^^^^^^^^^

.. automodule:: smartpool.core.managers.pool_operations_manager.PoolOperationResult
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: success, object_found, error_message, objects_processed

Metrics
-------

Performance Metrics
~~~~~~~~~~~~~~~~~~~

PerformanceMetrics
^^^^^^^^^^^^^^^^^^

.. automodule:: smartpool.core.metrics.performance_metrics
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: AcquisitionRecord, PerformanceSnapshot

AcquisitionRecord
^^^^^^^^^^^^^^^^^
.. automodule:: smartpool.core.metrics.performance_metrics.AcquisitionRecord
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: timestamp, acquisition_time_ms, lock_wait_time_ms, key, hit, validation_attempts

PerformanceSnapshot
^^^^^^^^^^^^^^^^^^^
.. automodule:: smartpool.core.metrics.performance_metrics.PerformanceSnapshot
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: timestamp, total_acquisitions, hit_rate, avg_acquisition_time_ms, min_acquisition_time_ms, max_acquisition_time_ms, p50_acquisition_time_ms, p95_acquisition_time_ms, p99_acquisition_time_ms, avg_lock_wait_time_ms, max_lock_wait_time_ms, lock_contention_rate, acquisitions_per_second, peak_concurrent_acquisitions, top_keys_by_usage, slowest_keys

Thread Safe stats
~~~~~~~~~~~~~~~~~

ThreadSafeStats
^^^^^^^^^^^^^^^

.. automodule:: smartpool.core.metrics.thread_safe_stats
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: PoolMetrics

PoolMetrics
^^^^^^^^^^^

.. automodule:: smartpool.core.metrics.thread_safe_stats.PoolMetrics
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: timestamp, hits, misses, creates, reuses, evictions, expired, corrupted, validation_failures, reset_failures, hit_rate, avg_object_age, pool_efficiency

Utils
-----

.. automodule:: smartpool.core.utils
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

Exceptions
----------

.. toctree::
   :maxdepth: 2
   :caption: Exceptions

   exceptions.rst