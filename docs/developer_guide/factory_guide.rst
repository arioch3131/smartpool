Factory Creation Guide
======================

This guide provides comprehensive instructions for creating custom factories for the adaptive memory pool system.

Introduction
------------

A factory is responsible for creating, resetting, validating, and destroying objects managed by the memory pool.
The factory pattern ensures consistent object lifecycle management and enables efficient pooling strategies.

Understanding the ObjectFactory Interface
-----------------------------------------

The abstract :py:class:`~smartpool.core.factory_interface.ObjectFactory` class defines the contract that all factories must implement. This interface ensures consistent object lifecycle management within the memory pool.

.. code-block:: python

   from abc import ABC, abstractmethod
   from typing import Generic, TypeVar
   import sys

   T = TypeVar("T")

   class ObjectFactory(ABC, Generic[T]):
       @abstractmethod
       def create(self, *args, **kwargs) -> T:
           """Create a new object instance.

           This method is responsible for instantiating a new object of type `T`.
           It can accept arbitrary positional and keyword arguments to allow for flexible
           object construction based on specific needs.
           """
           
       @abstractmethod  
       def reset(self, obj: T) -> bool:
           """Reset the object to its initial state for reuse.

           This method prepares an object for its next use by clearing any previous state.
           It should return `True` if the reset was successful, `False` otherwise.
           A failed reset will typically lead to the object being destroyed.
           """
           
       @abstractmethod
       def validate(self, obj: T) -> bool:
           """Validate object integrity and usability.

           This method checks if an object is still valid and usable by the pool.
           For example, a database connection might be validated by pinging the database.
           It should return `True` if the object is valid, `False` otherwise.
           """
           
       @abstractmethod
       def get_key(self, *args, **kwargs) -> str:
           """Generate a unique pooling key based on parameters.

           This method is crucial for identifying and grouping similar objects within the pool.
           The key should uniquely represent the type or configuration of the object being requested.
           For example, a database connection key might include the connection string.
           """
           
       def destroy(self, obj: T) -> None:
           """Clean up object resources (optional override).

           This method is called when an object is permanently removed from the pool.
           It should release any external resources held by the object (e.g., close a file handle,
           close a network connection). If not overridden, a default no-op implementation is used.
           """
           pass
           
       def estimate_size(self, obj: T) -> int:
           """Estimate object memory size in bytes (optional override).

           This method provides an estimated memory footprint of the object.
           This information can be used by the pool's memory management and optimization components.
           If not overridden, `sys.getsizeof()` is used as a default, which might not be accurate
           for complex objects.
           """
           return sys.getsizeof(obj)

Required Methods
----------------

**create(*args, **kwargs) -> T**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Creates and returns a new instance of the managed object type.

**Purpose:**
- Instantiate objects when the pool is empty or needs expansion
- Handle variable construction parameters via args/kwargs
- Return properly initialized objects ready for use

**Implementation Example:**

.. code-block:: python

   def create(self, *args, **kwargs) -> MyObject:
       # Extract parameters with default values
       size = args[0] if args else kwargs.get('size', 1024)
       mode = kwargs.get('mode', 'default')
       
       # Create and configure object
       obj = MyObject(size)
       obj.configure(mode=mode)
       return obj

**get_key(*args, **kwargs) -> str**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generates a unique key for pooling purposes based on the arguments provided for object creation.

**Purpose:**
- **Object Identification:** The key uniquely identifies a type or configuration of object within the pool. Objects requested with the same key are considered interchangeable.
- **Pooling Strategy:** Enables the pool to manage distinct groups of objects. For example, if you have database connections to different databases, their keys would reflect the connection string, allowing `smartpool` to maintain separate pools for each.
- **Flexibility:** Allows the pooling mechanism to adapt to various object types and their specific identification needs.

**Implementation Considerations:**
- The key should be deterministic: calling `get_key` with the same `*args` and `**kwargs` should always produce the same key.
- The key should be granular enough to differentiate between distinct object configurations, but not so granular that it defeats the purpose of pooling (e.g., don't include a timestamp in the key unless you intend to pool objects for a very short, specific time window).
- For objects like database connections, the key might be derived from the connection string or a hash of its relevant parameters.
- For image processing, the key might include image dimensions, color mode, or processing parameters.

**Example:**

.. code-block:: python

   def get_key(self, *args, **kwargs) -> str:
       # Example: Key based on image dimensions and mode
       width = kwargs.get('width')
       height = kwargs.get('height')
       mode = kwargs.get('mode', 'RGB')
       if width and height:
           return f"image_{width}x{height}_{mode}"
       return "default_image"

Optional Methods: `destroy` and `estimate_size`
-----------------------------------------------

While `create`, `reset`, `validate`, and `get_key` are mandatory for any `ObjectFactory` implementation, `destroy` and `estimate_size` are optional. Overriding these methods allows for more fine-grained control over resource management and memory accounting.

destroy(obj: T) -> None
~~~~~~~~~~~~~~~~~~~~~~~~

This method is invoked when an object is permanently removed from the pool, either due to explicit destruction, a failed reset/validation, or during pool shutdown.

**Purpose:**
- **Resource Release:** Crucial for releasing external resources held by the object (e.g., closing file handles, network sockets, database connections, or freeing large memory blocks).
- **Preventing Leaks:** Ensures that resources are properly cleaned up, preventing resource leaks and improving system stability.

**When to Override:**
- Always override if your pooled objects hold external resources that need explicit closing or cleanup.
- If your objects are simple Python objects that are garbage-collected automatically, overriding `destroy` might not be strictly necessary, but it's good practice for clarity and future extensibility.

**Example:**

.. code-block:: python

   def destroy(self, obj: MyResource) -> None:
       if obj and hasattr(obj, 'close'):
           obj.close() # Close a file, connection, etc.

estimate_size(obj: T) -> int
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This method provides an estimated memory footprint of the object in bytes. This information is used by `smartpool`'s internal memory management and optimization components.

**Purpose:**
- **Accurate Memory Accounting:** Allows the pool to keep a more accurate track of the memory consumed by pooled objects, which is vital for memory pressure detection and adaptive sizing.
- **Optimization Hints:** Provides data for the `MemoryOptimizer` to make informed decisions about pool sizing and object eviction strategies.

**When to Override:**
- Override this method if `sys.getsizeof(obj)` (the default implementation) does not accurately reflect the total memory consumed by your object. This is often the case for objects that hold large internal buffers, external data, or complex nested structures (e.g., NumPy arrays, PIL images, large dataframes).
- If your objects are simple and `sys.getsizeof()` is sufficient, you don't need to override it.

**Example:**

.. code-block:: python

   def estimate_size(self, obj: MyImage) -> int:
       # Example for a PIL Image object
       if obj:
           # Estimate size based on image dimensions and pixel depth
           return obj.width * obj.height * (len(obj.mode) if obj.mode else 1)
       return 0

Best Practices
--------------

1. **Thread Safety**: Ensure your factory methods are thread-safe
2. **Resource Management**: Always implement proper cleanup in ``destroy()`` methods
3. **Error Handling**: Handle exceptions gracefully in factory methods
4. **Performance**: Keep object creation and reset operations lightweight
5. **Validation**: Implement thorough validation to catch issues early

For more detailed examples and advanced patterns, see the :doc:`../examples/advanced_patterns` section.

Concrete Factory Example: SQLAlchemySessionFactory
--------------------------------------------------

The :py:class:`~examples.factories.database.sqlalchemy_session_factory.SQLAlchemySessionFactory` serves as a practical example of implementing a custom `ObjectFactory` for managing SQLAlchemy database sessions.

**Key Aspects:**
- **`session_source`:** The factory is initialized with a `session_source`, which can be a SQLAlchemy `sessionmaker`, an object with a `.session` attribute, or an object with a `.create_session` method. This flexible design allows integration with various database setup patterns.
- **`create` Method:** Dynamically creates a new SQLAlchemy session based on the `session_source` type.
- **`reset` Method:** Rolls back any pending transactions and expunges all objects from the session, ensuring a clean state for reuse. This is crucial for maintaining data integrity across session reuses.
- **`validate` Method:** Checks if the session is still active and usable (e.g., `session.is_active`).
- **`get_key` Method:** Returns a fixed key "session_default", indicating that all sessions created by this factory are considered interchangeable for pooling purposes. For more complex scenarios (e.g., pooling connections to different databases), this method would be extended to generate keys based on connection parameters.

This example highlights how `smartpool` can be used to efficiently manage expensive and stateful resources like database connections, ensuring they are reused effectively and returned to a clean state.
