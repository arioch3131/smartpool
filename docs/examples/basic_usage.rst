Basic Usage Examples
====================

Creating a Simple Object Factory
--------------------------------

Start by creating a factory for the objects you want to pool:

.. code-block:: python

   from smartpool import SmartObjectManager, ObjectFactory, MemoryConfig

   class SimpleDataFactory(ObjectFactory):
       def create(self, *args, **kwargs):
           size = args[0] if args else kwargs.get("size", 1024)
           return {
               "buffer": bytearray(size),
               "metadata": {},
               "size": size
           }
       
       def reset(self, obj):
           obj["buffer"][:] = b"\0" * len(obj["buffer"])
           obj["metadata"].clear()
           return True
       
       def validate(self, obj):
           return (isinstance(obj, dict) and 
                   "buffer" in obj and 
                   "metadata" in obj)
       
       def get_key(self, *args, **kwargs):
           size = args[0] if args else kwargs.get("size", 1024)
           return f"data_{size}"

   # Use the factory
   factory = SimpleDataFactory()
   config = MemoryConfig(max_objects_per_key=10, enable_logging=True)
   pool = SmartObjectManager(factory, default_config=config)

   # Process data
   with pool.acquire_context(2048) as data_obj:
       data_obj["buffer"][:10] = b"Hello Data"
       data_obj["metadata"]["processed_at"] = "2025-01-15"
       print(f"Processed {len(data_obj['buffer'])} bytes")

   pool.shutdown()

BytesIO Example (From examples/)
--------------------------------

Copy this pattern from examples/factories/basic/bytesio_factory.py:

.. code-block:: python

   from io import BytesIO
   from smartpool import SmartObjectManager, ObjectFactory

   class BytesIOFactory(ObjectFactory[BytesIO]):
       def create(self, *args, **kwargs):
           initial_size = args[0] if args else kwargs.get("initial_size", 0)
           buffer = BytesIO()
           if initial_size > 0:
               buffer.write(b"\0" * initial_size)
               buffer.seek(0)
           return buffer
       
       def reset(self, obj):
           try:
               obj.seek(0)
               obj.truncate(0)
               return True
           except IOError:
               return False
       
       def validate(self, obj):
           return isinstance(obj, BytesIO) and not obj.closed
       
       def get_key(self, *args, **kwargs):
           initial_size = args[0] if args else kwargs.get("initial_size", 0)
           if initial_size < 1024:
               return "bytesio_0"
           return f"bytesio_{(initial_size // 1024) * 1024}"

   # Use it
   factory = BytesIOFactory()
   pool = SmartObjectManager(factory)

   for i in range(5):
       with pool.acquire_context(1024) as buffer:
           buffer.write(f"Message {i}".encode())
           buffer.seek(0)
           print(f"Content: {buffer.read().decode()}")

   pool.shutdown()

Performance Monitoring
----------------------

Monitor your pool's performance:

.. code-block:: python

   from smartpool import MemoryConfig
   
   # Create pool with metrics enabled
   config = MemoryConfig(enable_performance_metrics=True)
   pool = SmartObjectManager(BytesIOFactory(), default_config=config)

   # Do some work
   for i in range(100):
       with pool.acquire_context(1024) as buffer:
           buffer.write(f"Data {i}".encode())

   # Check performance
   stats = pool.get_basic_stats()
   hit_rate = stats['counters']['hits'] / (stats['counters']['hits'] + stats['counters']['misses']) * 100
   print(f"Hit rate: {hit_rate:.1f}%")
   print(f"Objects pooled: {stats['total_pooled_objects']}")

   pool.shutdown()

Adapting Example Factories
--------------------------

To use factories from examples/:

1. Browse examples/factories/ to find relevant patterns
2. Copy the factory code to your project
3. Modify as needed for your requirements
4. Install only the dependencies you need

.. code-block:: bash

   # Only install what you need
   pip install smartpool              # Core (zero dependencies)
   pip install Pillow                 # If using image factories
   pip install numpy                  # If using array factories
   pip install SQLAlchemy            # If using database factories
