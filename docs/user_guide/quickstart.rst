Quick Start
===========

Basic Usage with Custom Factory
-------------------------------

SmartPool is designed to be adapted to any object type. Create a factory for your objects:

.. code-block:: python

   from smartpool import SmartObjectManager, ObjectFactory, MemoryPreset

   # Create a custom factory for any object type
   class MyObjectFactory(ObjectFactory):
       def create(self, *args, **kwargs):
           # Create your object here
           return {"data": None, "size": args[0] if args else 1024}
       
       def reset(self, obj):
           # Reset object state for reuse
           obj["data"] = None
           return True
       
       def validate(self, obj):
           # Check if object is valid
           return isinstance(obj, dict) and "data" in obj
       
       def get_key(self, *args, **kwargs):
           # Group similar objects together
           size = args[0] if args else 1024
           return f"myobj_{size}"

   # Use your custom factory
   factory = MyObjectFactory()
   pool = SmartObjectManager(factory=factory, preset=MemoryPreset.HIGH_THROUGHPUT)

   # Use the pool
   with pool.acquire_context(1024) as obj:
       obj["data"] = "Hello, SmartPool!"
       print(f"Object: {obj}")

   # Shutdown when done
   pool.shutdown()

Example Factories for Inspiration
---------------------------------

The examples/factories/ directory contains reference implementations:

**Basic Objects** (examples/factories/basic/):

* **BytesIOFactory**: For io.BytesIO buffer objects
* **MetadataFactory**: For metadata dictionaries
* **QueryResultFactory**: For database query results

**Advanced Examples** (requires additional dependencies):

* **PILImageFactory**: For PIL image objects (requires Pillow)
* **NumpyArrayFactory**: For NumPy arrays (requires numpy)
* **SQLAlchemySessionFactory**: For database sessions (requires SQLAlchemy)

**How to Use Example Factories:**

1. **Copy** the relevant factory code from examples/factories/
2. **Adapt** it to your specific needs
3. **Install** only the dependencies you actually need

Why This Architecture?
----------------------

**Zero Dependencies**: SmartPool core has no external dependencies.

**Maximum Flexibility**: Adapt to any object type.

**Lightweight**: Include only the factories you use.

**Inspiration**: Examples show best practices.

Next Steps
----------

1. Check examples/factories/ for factories similar to your use case
2. Copy and adapt the relevant factory code
3. See the :doc:`../api/core` for detailed API documentation
4. Read :doc:`../examples/basic_usage` for more patterns
