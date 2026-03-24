Advanced Usage Patterns
=======================

This section explores advanced usage patterns and techniques for fine-tuning `smartpool`'s behavior, optimizing performance, and integrating with complex application workflows.

Using Configuration Presets
---------------------------
`smartpool` provides predefined configuration presets to quickly adapt the pool's behavior for common use cases. This example demonstrates how to initialize a pool with different presets and inspect their configurations.

.. code-block:: python

   from smartpool import SmartObjectManager, MemoryPreset
   from examples.factories import BytesIOFactory

   factory = BytesIOFactory()

   # Initialize pool with a specific preset
   pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

   # Get preset information and configuration
   preset_info = pool.get_preset_info()
   config = pool.default_config

   print(f"Preset: {preset_info['name']}")
   print(f"Description: {preset_info['description']}")
   print(f"Max objects per key: {config.max_objects_per_key}")

   # ... perform operations ...

   pool.shutdown()

Automatic Optimization
----------------------
`smartpool` can automatically adjust its configuration based on observed performance metrics, optimizing for efficiency and resource utilization. This example shows how to enable and observe the auto-tuning mechanism.

.. code-block:: python

   from smartpool import SmartObjectManager, MemoryConfig
   from examples.factories import BytesIOFactory
   import time

   factory = BytesIOFactory()
   config = MemoryConfig(
       max_objects_per_key=10, # Intentionally small to trigger optimization
       enable_performance_metrics=True,
       enable_acquisition_tracking=True,
   )
   pool = SmartObjectManager(factory, default_config=config)

   try:
       # Enable auto-tuning
       pool.enable_auto_tuning(interval_seconds=3.0)

       print("Generating load to trigger optimization...")
       for i in range(100):
           with pool.acquire_context(1024) as buffer:
               buffer.write(f"Load {i}".encode())
           time.sleep(0.01)

       time.sleep(4.0) # Allow auto-tuning to run

       tuning_info = pool.optimizer.get_tuning_info()
       print(f"Adjustments made: {tuning_info['adjustments_count']}")
       if tuning_info["history"]:
           print("Last adjustment:", tuning_info["history"][-1]["adjustments"])

   finally:
       pool.shutdown()

Real-time Monitoring
--------------------
Monitor the pool's performance and statistics in real-time, providing insights into its operational health and efficiency under concurrent loads.

.. code-block:: python

   from smartpool import SmartObjectManager, MemoryConfig
   from examples.factories import BytesIOFactory
   import threading
   import time
   from concurrent.futures import ThreadPoolExecutor

   factory = BytesIOFactory()
   config = MemoryConfig(
       max_objects_per_key=15,
       enable_performance_metrics=True,
       enable_acquisition_tracking=True,
   )
   pool = SmartObjectManager(factory, default_config=config)

   monitoring_active = True

   def monitor_loop():
       while monitoring_active:
           if pool.performance_metrics:
               snapshot = pool.performance_metrics.create_snapshot()
               stats = pool.get_basic_stats()
               print(f"Active: {stats.get('active_objects_count')}, Pooled: {stats.get('total_pooled_objects')}, Hit rate: {snapshot.hit_rate:.1%}")
           time.sleep(1.0)

   monitor_thread = threading.Thread(target=monitor_loop)
   monitor_thread.start()

   try:
       with ThreadPoolExecutor(max_workers=5) as executor:
           for worker_id in range(5):
               executor.submit(lambda w_id: [pool.acquire_context(1024).buffer.write(f"Worker {w_id}".encode()) for _ in range(20)], worker_id)
       
       # Wait for workers to finish (simplified for doc)
       time.sleep(5)

   finally:
       monitoring_active = False
       monitor_thread.join()
       pool.shutdown()

Generating Detailed Reports
---------------------------
Generate comprehensive performance reports, including basic statistics, current metrics, alerts, recommendations, and detailed statistics by object key.

.. code-block:: python

   from smartpool import SmartObjectManager, MemoryPreset
   from examples.factories import BytesIOFactory

   factory = BytesIOFactory()
   pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

   try:
       # Simulate workload
       for i in range(50):
           size = [512, 1024, 2048][i % 3]
           with pool.acquire_context(size) as buffer:
               buffer.write(f"Data {i}".encode())

       perf_report = pool.get_performance_report(detailed=True);

       print("--- Full Performance Report ---")
       print(f"Hit rate: {perf_report['performance']['current_metrics']['hit_rate']:.2%}")
       print(f"Alerts: {len(perf_report['performance']['alerts'])}")
       print(f"Recommendations: {len(perf_report['performance']['recommendations'])}")

       # Access other parts of the report like basic_stats, config, key_statistics, health_status, dashboard_summary

   finally:
       pool.shutdown()

Advanced Custom Configuration
-----------------------------
Beyond presets, `smartpool` allows for highly granular custom configurations, enabling precise control over pool behavior, resource management, and performance characteristics.

.. code-block:: python

   from smartpool import SmartObjectManager, MemoryConfig, ObjectCreationCost, MemoryPressure
   from examples.factories import BytesIOFactory

   factory = BytesIOFactory()
   custom_config = MemoryConfig(
       max_objects_per_key=30,
       ttl_seconds=1200.0,
       enable_logging=True,
       max_expected_concurrency=25,
       object_creation_cost=ObjectCreationCost.MEDIUM,
       memory_pressure=MemoryPressure.NORMAL,
   )
   pool = SmartObjectManager(factory, default_config=custom_config)

   try:
       print("Custom configuration applied.")
       print(f"Max objects per key: {pool.default_config.max_objects_per_key}")

       # Perform operations with the custom configured pool
       with pool.acquire_context(1024) as buffer:
           buffer.write(b"Custom config test")

   finally:
       pool.shutdown()
