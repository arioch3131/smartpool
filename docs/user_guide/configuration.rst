Configuration Guide
===================

This guide details the various configuration options available for `smartpool`, allowing you to fine-tune its behavior to match your application's specific needs and optimize resource utilization.

SmartPool's configuration is managed primarily through the :py:class:`~smartpool.config.MemoryConfig` class and its associated factory, :py:class:`~smartpool.config.MemoryConfigFactory`.

MemoryConfig Parameters
-----------------------

The :py:class:`~smartpool.config.MemoryConfig` dataclass encapsulates all configurable parameters of the memory pool. Understanding these parameters is key to effective tuning.

.. py:class:: smartpool.config.MemoryConfig
   :module: smartpool.config

   .. autoattribute:: max_objects_per_key
   .. autoattribute:: ttl_seconds
   .. autoattribute:: cleanup_interval_seconds
   .. autoattribute:: enable_logging
   .. autoattribute:: enable_background_cleanup
   .. autoattribute:: max_validation_attempts
   .. autoattribute:: max_corrupted_objects
   .. autoattribute:: enable_performance_metrics
   .. autoattribute:: enable_acquisition_tracking
   .. autoattribute:: enable_lock_contention_tracking
   .. autoattribute:: max_performance_history_size
   .. autoattribute:: max_expected_concurrency
   .. autoattribute:: object_creation_cost
   .. autoattribute:: memory_pressure

Configuration Presets
---------------------

`smartpool` provides several predefined configuration presets, accessible via :py:class:`~smartpool.config.MemoryPreset`, that are optimized for common use cases. These presets offer a quick way to apply a set of recommended settings without manually configuring each parameter.

To get a description of each preset's recommended use case, you can refer to :py:meth:`~smartpool.config.MemoryConfigFactory.get_preset_recommendations`.

Here are the available presets and their general characteristics:

*   **HIGH_THROUGHPUT**: Applications with high load requiring fast response times. Optimized to reduce object creations and contentions.
*   **LOW_MEMORY**: Environments with strict memory constraints. Minimal pool with aggressive cleanup.
*   **IMAGE_PROCESSING**: Image processing or large objects. Balance between performance and memory consumption.
*   **DATABASE_CONNECTIONS**: DB connection pools or network resources. Strict validation and maximum reuse.
*   **BATCH_PROCESSING**: Batch processing or long tasks. Optimized for stability over long periods.
*   **DEVELOPMENT**: Development and testing. Full logging and early problem detection.
*   **CUSTOM**: Custom configuration for specific needs.

Custom Configuration
--------------------

You can create a custom configuration by instantiating :py:class:`~smartpool.config.MemoryConfig` directly and passing your desired values. Any parameters not explicitly set will use their default values.

.. code-block:: python

   from smartpool.config import MemoryConfig, ObjectCreationCost, MemoryPressure

   my_custom_config = MemoryConfig(
       max_objects_per_key=50,
       ttl_seconds=120.0,
       enable_logging=True,
       object_creation_cost=ObjectCreationCost.HIGH,
       memory_pressure=MemoryPressure.NORMAL,
   )

Dynamic Configuration Changes
-----------------------------

`smartpool` allows for dynamic adjustment of its configuration at runtime through the :py:meth:`~smartpool.core.managers.memory_manager.MemoryManager.switch_preset` method. This enables you to adapt the pool's behavior based on changing application load or environmental conditions without restarting the application.

.. code-block:: python

   from smartpool import SmartObjectManager
   from smartpool.config import MemoryPreset

   # Assuming 'pool_manager' is an instance of SmartObjectManager
   # pool_manager = SmartObjectManager(...)

   # Switch to a different preset dynamically
   pool_manager.memory_manager.switch_preset(MemoryPreset.LOW_MEMORY)

   # You can also apply custom configurations dynamically
   # new_custom_config = MemoryConfig(...)
   # pool_manager.memory_manager.switch_preset(MemoryPreset.CUSTOM, config=new_custom_config)

For more advanced auto-tuning capabilities, refer to the :doc:`../developer_guide/architecture` section on the Memory Optimizer.