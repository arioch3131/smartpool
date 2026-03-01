Extending SmartPool
===================

Learn how to extend SmartPool with custom functionality.

Creating Custom Factories
-------------------------

The most common way to extend SmartPool is by creating custom factories.
See the :doc:`factory_guide` for detailed instructions.

Custom Managers
---------------

For advanced use cases, you can create custom pool managers:

.. code-block:: python

   from smartpool.core.smartpool_manager import SmartObjectManager

   class CustomManager(SmartObjectManager):
       def __init__(self, *args, **kwargs):
           super().__init__(*args, **kwargs)
           # Custom initialization
       
       def custom_optimization(self):
           # Your custom logic here
           pass

Custom Metrics
--------------

Add custom metrics to monitor specific behaviors. You can extend `ThreadSafeStats` to add your own counters or gauges:

.. code-block:: python

   from smartpool.core.metrics.thread_safe_stats import ThreadSafeStats

   class CustomStats(ThreadSafeStats):
       def __init__(self):
           super().__init__()
           self.custom_counter = 0
       
       def increment_custom(self):
           self.custom_counter += 1

Integration Patterns
--------------------

Database Integration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Example with SQLAlchemy
   from examples.factories.database.sqlalchemy_session_factory import SQLAlchemySessionFactory
   
   # You would typically use this factory with your SQLAlchemy engine/sessionmaker
   # For example:
   # from sqlalchemy import create_engine
   # from sqlalchemy.orm import sessionmaker
   # engine = create_engine("sqlite:///:memory:")
   # Session = sessionmaker(bind=engine)
   # my_factory = SQLAlchemySessionFactory(Session)

Web Framework Integration
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Example with Flask/FastAPI
   from smartpool.core.smartpool_manager import SmartObjectManager
   
   # Initialize pool at application startup
   app_pool = SmartObjectManager(factory=YourFactory())
   
   # Use in request handlers
   @app.route("/api/data")
   def handle_request():
       with app_pool.acquire_context() as obj:
           return obj.process_request()

Best Practices
--------------

1. **Thread Safety**: Ensure your custom components are thread-safe
2. **Resource Cleanup**: Always implement proper cleanup in ``destroy()`` methods
3. **Error Handling**: Handle exceptions gracefully in factory methods
4. **Testing**: Write comprehensive tests for custom components
5. **Documentation**: Document your extensions thoroughly
