Framework Integrations
======================

This section provides examples of integrating `smartpool` with popular Python frameworks, demonstrating its use in real-world application scenarios.

Image Processing Service with FastAPI
-------------------------------------
This comprehensive example showcases `smartpool`'s capabilities within an image processing service built using FastAPI. It demonstrates how to leverage multiple memory pools for different object types (images, I/O buffers, metadata cache), enable real-time monitoring and auto-optimization, and expose these functionalities via a REST API.

**Key `smartpool` Features Demonstrated:**

*   **Multiple Pools:** Manages separate pools for `PIL.Image` objects, `io.BytesIO` buffers, and metadata dictionaries.
*   **Configurable Pools:** Each pool is configured with specific `MemoryConfig` or `MemoryPreset` (e.g., `IMAGE_PROCESSING`, `HIGH_THROUGHPUT`).
*   **Auto-Optimization:** Pools are configured to automatically adjust their parameters based on observed performance metrics.
*   **Real-time Monitoring:** Exposes pool health and performance metrics via dedicated API endpoints.
*   **Resource Management:** Efficiently reuses expensive resources like image objects and I/O buffers, reducing memory allocations and garbage collection overhead.

**Example Structure:**

The example is structured into several components:

*   **`AppConfig`**: Application-level configuration.
*   **`PoolManager`**: Centralized manager for initializing, retrieving, and shutting down all `smartpool` instances. It also provides aggregated health and performance summaries.
*   **`ImageProcessingService`**: Business logic for image processing, which heavily utilizes the `smartpool` instances for image objects, buffers, and caching.
*   **`ImageProcessingApp` (FastAPI)**: The web application layer that exposes REST endpoints for image upload, processing, download, and monitoring.

**Running the Example:**

To run this example, you need to install the additional dependencies specified in `pyproject.toml` under the `[project.optional-dependencies.examples]` group.

1.  **Install Dependencies:**

    .. code-block:: bash

       pip install -e ".[examples]"

2.  **Navigate to the Example Directory:**

    .. code-block:: bash

       cd examples

3.  **Run the Example:**

    The `example_10_complete_integration.py` file contains a `main` block that demonstrates both a direct application run (without the FastAPI server) and an API usage overview.

    .. code-block:: bash

       python example_10_complete_integration.py

    This will execute the `demo_complete_application()` (which simulates the image processing workflow) and `demo_api_usage()` (which prints API endpoints and `curl` examples).

**Core Pool Initialization (from `PoolManager`):**

.. code-block:: python

   from smartpool import MemoryConfig, MemoryPreset, SmartObjectManager, PoolConfiguration, ObjectCreationCost, MemoryPressure
   from examples.factories import BytesIOFactory, MetadataFactory, PILImageFactory

   # Pool for PIL images
   image_factory = PILImageFactory(enable_reset=True)
   image_config = MemoryConfig(
       max_objects_per_key=50,
       ttl_seconds=1800.0,
       enable_performance_metrics=True,
       enable_acquisition_tracking=True,
       max_expected_concurrency=20,
       object_creation_cost=ObjectCreationCost.HIGH,
       memory_pressure=MemoryPressure.NORMAL,
   )
   self.pools["images"] = SmartObjectManager(
       image_factory,
       default_config=image_config,
       pool_config=PoolConfiguration(max_total_objects=150, enable_monitoring=True),
   )

   # Pool for I/O buffers
   buffer_factory = BytesIOFactory()
   self.pools["buffers"] = SmartObjectManager(
       buffer_factory, preset=MemoryPreset.HIGH_THROUGHPUT
   )

   # Pool for metadata cache
   metadata_factory = MetadataFactory()
   cache_config = MemoryConfig(
       max_objects_per_key=200, ttl_seconds=3600.0, enable_performance_metrics=True
   )
   self.pools["cache"] = SmartObjectManager(metadata_factory, default_config=cache_config)

   # Enable auto-optimization
   for pool_name, pool in self.pools.items():
       pool.enable_auto_tuning(interval_seconds=300.0)

**Example API Endpoints:**

The FastAPI application exposes several endpoints for interacting with the service and monitoring the pools:

*   `POST /upload`: Upload an image and create a processing job.
*   `POST /process/{job_id}`: Trigger the processing of a job.
*   `GET /jobs/{job_id}`: Get the status of a specific job.
*   `GET /download/{job_id}`: Download the processed image.
*   `GET /health`: Get the overall health status of the application and its pools.
*   `GET /metrics`: Get performance metrics for all pools and application-level job statistics.
*   `GET /pools/{pool_name}/status`: Get detailed status for a specific pool.
*   `POST /pools/{pool_name}/optimize`: Manually trigger optimization for a pool.

This example provides a robust foundation for building high-performance, resource-efficient applications using `smartpool`.
