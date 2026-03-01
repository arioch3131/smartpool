# Factory Creation Guide - Adaptive Memory Pool

## Introduction

This guide provides comprehensive instructions for creating custom factories for the adaptive memory pool system. A factory is responsible for creating, resetting, validating, and destroying objects managed by the memory pool.

## Understanding the ObjectFactory Interface

The `ObjectFactory` abstract base class defines the contract that all factories must implement:

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
import sys

T = TypeVar("T")

class ObjectFactory(ABC, Generic[T]):
    @abstractmethod
    def create(self, *args, **kwargs) -> T:
        """Create a new object instance."""
        
    @abstractmethod  
    def reset(self, obj: T) -> bool:
        """Reset object to initial state for reuse."""
        
    @abstractmethod
    def validate(self, obj: T) -> bool:
        """Validate object integrity and usability."""
        
    @abstractmethod
    def get_key(self, *args, **kwargs) -> str:
        """Generate unique pooling key based on parameters."""
        
    def destroy(self, obj: T) -> None:
        """Clean up object resources (optional override)."""
        pass
        
    def estimate_size(self, obj: T) -> int:
        """Estimate object memory size (optional override)."""
        return sys.getsizeof(obj)
```

## Required Methods

### 1. create(*args, **kwargs) -> T

Creates and returns a new instance of the managed object type.

**Purpose:**
- Instantiate objects when the pool is empty or needs expansion
- Handle variable construction parameters through args/kwargs
- Return properly initialized objects ready for use

**Implementation Guidelines:**
```python
def create(self, *args, **kwargs) -> MyObject:
    # Extract parameters with defaults
    size = args[0] if args else kwargs.get('size', 1024)
    mode = kwargs.get('mode', 'default')
    
    # Create and configure object
    obj = MyObject(size)
    obj.configure(mode=mode)
    return obj
```

**Best Practices:**
- Handle both positional and keyword arguments gracefully
- Provide sensible defaults for missing parameters
- Validate input parameters and raise clear exceptions for invalid inputs
- Keep creation lightweight to avoid pool performance penalties

### 2. reset(obj: T) -> bool

Resets an object to a clean, reusable state before returning it to the pool.

**Purpose:**
- Clear transient state from previous usage
- Restore object to initial configuration
- Prepare object for next pool acquisition

**Return Value:**
- `True`: Object successfully reset and ready for reuse
- `False`: Reset failed, object should be destroyed

**Implementation Guidelines:**
```python
def reset(self, obj: MyObject) -> bool:
    try:
        # Clear data structures
        obj.data.clear()
        
        # Reset state variables
        obj.position = 0
        obj.mode = 'default'
        
        # Reset any streams or buffers
        if hasattr(obj, 'buffer'):
            obj.buffer.seek(0)
            obj.buffer.truncate(0)
            
        return True
    except (AttributeError, TypeError, IOError):
        return False
```

**Best Practices:**
- Handle all possible exceptions gracefully
- Reset expensive-to-recreate state while preserving structure
- Verify object integrity during reset process
- Keep reset operations fast to minimize pool overhead

### 3. validate(obj: T) -> bool

Validates that an object is in a usable state and suitable for pool management.

**Purpose:**
- Verify object integrity before acquisition from pool
- Check for corruption or invalid state
- Ensure object meets requirements for reuse

**Return Value:**
- `True`: Object is valid and can be used
- `False`: Object is invalid and should be destroyed

**Implementation Guidelines:**
```python
def validate(self, obj: MyObject) -> bool:
    try:
        # Type check
        if not isinstance(obj, MyObject):
            return False
            
        # State validation
        if not hasattr(obj, 'data') or obj.data is None:
            return False
            
        # Functional validation
        if hasattr(obj, 'is_connected'):
            if not obj.is_connected():
                return False
                
        # Size limits
        if len(obj.data) > self.MAX_SIZE:
            return False
            
        return True
    except (AttributeError, TypeError):
        return False
```

**Best Practices:**
- Check object type and essential attributes
- Validate functional state (connections, file handles, etc.)
- Test critical operations without side effects
- Return False for any uncertainty rather than risking corruption

### 4. get_key(*args, **kwargs) -> str

Generates a unique string key that groups similar objects together for efficient pooling.

**Purpose:**
- Enable pool segmentation by object characteristics
- Group objects with similar creation parameters
- Optimize pool efficiency through appropriate categorization

**Implementation Guidelines:**
```python
def get_key(self, *args, **kwargs) -> str:
    # Simple key based on primary parameter
    size = args[0] if args else kwargs.get('size', 1024)
    return f"myobject_{size}"
    
    # Complex key with multiple parameters
    size = args[0] if args else kwargs.get('size', 1024)
    mode = kwargs.get('mode', 'default')
    return f"myobject_{size}_{mode}"
    
    # Size range grouping for efficiency
    size = args[0] if args else kwargs.get('size', 1024)
    size_bucket = (size // 1024) * 1024  # Round to nearest KB
    return f"myobject_{size_bucket}"
```

**Best Practices:**
- Include parameters that significantly affect object characteristics
- Group similar sizes together using buckets for efficiency
- Keep keys short but descriptive
- Ensure consistent key generation for identical parameters
- Avoid including highly variable parameters that would prevent pooling

## Optional Methods

### destroy(obj: T) -> None

Cleans up object resources before permanent disposal.

**When to Override:**
- Objects hold external resources (file handles, database connections, network sockets)
- Objects have registered callbacks or listeners
- Objects maintain references to other resources

**Implementation Example:**
```python
def destroy(self, obj: MyObject) -> None:
    try:
        # Close external resources
        if hasattr(obj, 'connection') and obj.connection:
            obj.connection.close()
            
        # Unregister callbacks
        if hasattr(obj, 'unregister'):
            obj.unregister()
            
        # Clear large data structures
        if hasattr(obj, 'large_data'):
            obj.large_data.clear()
    except Exception:
        # Log error but don't raise - object is being destroyed anyway
        pass
```

### estimate_size(obj: T) -> int

Provides memory size estimation for pool management and reporting.

**When to Override:**
- Default `sys.getsizeof()` is insufficient for your object type
- Object holds complex nested data structures
- Accurate memory tracking is important for your use case

**Implementation Example:**
```python
def estimate_size(self, obj: MyObject) -> int:
    base_size = sys.getsizeof(obj)
    
    # Add size of contained data
    if hasattr(obj, 'data') and obj.data:
        base_size += sys.getsizeof(obj.data)
        if isinstance(obj.data, dict):
            for k, v in obj.data.items():
                base_size += sys.getsizeof(k) + sys.getsizeof(v)
    
    return base_size
```

## Complete Factory Example

Here's a complete implementation of a factory for configuration objects:

```python
import time
import sys
from typing import Dict, Any
from dataclasses import dataclass, field
from smartpool.core.factory_interface import ObjectFactory

@dataclass
class ConfigObject:
    """Configuration object with dictionary storage and metadata."""
    name: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    version: int = 1
    _dirty: bool = field(default=False, init=False)
    
    def set_setting(self, key: str, value: Any):
        self.settings[key] = value
        self._dirty = True
    
    def get_setting(self, key: str, default=None):
        return self.settings.get(key, default)
    
    def is_valid(self) -> bool:
        return (isinstance(self.settings, dict) and 
                isinstance(self.name, str) and 
                self.version > 0)

class ConfigObjectFactory(ObjectFactory[ConfigObject]):
    """Factory for configuration objects with intelligent pooling."""
    
    MAX_SETTINGS_SIZE = 1000  # Maximum number of settings
    
    def create(self, *args, **kwargs) -> ConfigObject:
        """Create new configuration object."""
        name = args[0] if args else kwargs.get('name', 'default')
        initial_settings = kwargs.get('settings', {})
        
        config_obj = ConfigObject(name=name)
        config_obj.settings.update(initial_settings)
        return config_obj
    
    def reset(self, obj: ConfigObject) -> bool:
        """Reset configuration object for reuse."""
        try:
            # Clear dynamic data but preserve structure
            obj.settings.clear()
            obj.name = ""
            obj.version = 1
            obj._dirty = False
            obj.created_at = time.time()
            return True
        except (AttributeError, TypeError):
            return False
    
    def validate(self, obj: ConfigObject) -> bool:
        """Validate configuration object integrity."""
        try:
            # Type and structure validation
            if not isinstance(obj, ConfigObject):
                return False
                
            # State validation
            if not obj.is_valid():
                return False
                
            # Size limits
            if len(obj.settings) > self.MAX_SETTINGS_SIZE:
                return False
                
            return True
        except (AttributeError, TypeError):
            return False
    
    def get_key(self, *args, **kwargs) -> str:
        """Generate pooling key based on expected usage pattern."""
        # Group by name pattern for similar configurations
        name = args[0] if args else kwargs.get('name', 'default')
        
        # Create categories for better pooling
        if name.startswith('user_'):
            return "config_user"
        elif name.startswith('system_'):
            return "config_system"
        else:
            return "config_default"
    
    def estimate_size(self, obj: ConfigObject) -> int:
        """Estimate memory usage including nested data."""
        base_size = sys.getsizeof(obj)
        
        # Add settings dictionary size
        if obj.settings:
            base_size += sys.getsizeof(obj.settings)
            for key, value in obj.settings.items():
                base_size += sys.getsizeof(key) + sys.getsizeof(value)
        
        return base_size
```

## Integration with Memory Pool

Once your factory is implemented, integrate it with the memory pool system:

```python
from smartpool.core.smartpool_manager import SmartObjectManager
from smartpool.config import MemoryPreset

# Create factory instance
factory = ConfigObjectFactory()

# Create memory pool with factory
pool = SmartObjectManager(
    factory=factory,
    preset=MemoryPreset.HIGH_THROUGHPUT
)

# Use the pool
with pool.acquire_context('user_profile', settings={'theme': 'dark'}) as config:
    config.set_setting('language', 'en')
    value = config.get_setting('theme')
    # Object automatically returned to pool when context exits

# Shutdown pool when done
pool.shutdown()
```

## Common Patterns and Best Practices

### Error Handling
```python
def reset(self, obj: T) -> bool:
    try:
        # Reset operations
        return True
    except Exception as e:
        # Log the error if needed, but don't raise
        logger.warning(f"Reset failed for {type(obj)}: {e}")
        return False
```

### Parameter Validation
```python
def create(self, *args, **kwargs) -> T:
    # Validate required parameters
    if not args and 'required_param' not in kwargs:
        raise ValueError("required_param must be provided")
    
    # Sanitize and validate inputs
    size = args[0] if args else kwargs.get('size', 1024)
    if size <= 0:
        raise ValueError("size must be positive")
```

### Efficient Key Generation
```python
def get_key(self, *args, **kwargs) -> str:
    # Use size buckets for better pooling
    size = args[0] if args else kwargs.get('size', 1024)
    bucket = ((size - 1) // 1024 + 1) * 1024  # Round up to next KB
    mode = kwargs.get('mode', 'default')
    return f"myobject_{bucket}_{mode}"
```

### Resource Management
```python
def destroy(self, obj: T) -> None:
    # Always use try-except in destroy methods
    try:
        if hasattr(obj, 'cleanup'):
            obj.cleanup()
    except Exception:
        pass  # Ignore errors during destruction
```

## Testing Your Factory

Create comprehensive tests for your factory implementation:

```python
import unittest
from unittest.mock import Mock

class TestConfigObjectFactory(unittest.TestCase):
    def setUp(self):
        self.factory = ConfigObjectFactory()
    
    def test_create_with_args(self):
        obj = self.factory.create('test_config')
        self.assertEqual(obj.name, 'test_config')
        self.assertIsInstance(obj.settings, dict)
    
    def test_create_with_kwargs(self):
        obj = self.factory.create(name='test', settings={'key': 'value'})
        self.assertEqual(obj.name, 'test')
        self.assertEqual(obj.settings['key'], 'value')
    
    def test_reset_success(self):
        obj = self.factory.create('test')
        obj.settings['key'] = 'value'
        obj_is_dirty = True
        
        result = self.factory.reset(obj)
        self.assertTrue(result)
        self.assertEqual(len(obj.settings), 0)
        self.assertFalse(obj._dirty)
    
    def test_validate_valid_object(self):
        obj = self.factory.create('test')
        self.assertTrue(self.factory.validate(obj))
    
    def test_validate_invalid_object(self):
        self.assertFalse(self.factory.validate("not a config object"))
        self.assertFalse(self.factory.validate(None))
    
    def test_key_generation(self):
        key1 = self.factory.get_key('user_profile')
        key2 = self.factory.get_key('user_settings')
        self.assertEqual(key1, key2)  # Both should use 'config_user'
```

## Performance Considerations

### Efficient Reset Operations
- Clear containers instead of recreating them
- Reset simple variables to default values
- Avoid expensive operations in reset methods

### Smart Key Generation
- Group similar objects together for better reuse
- Avoid over-granular keys that prevent pooling
- Use size buckets for numeric parameters

### Memory Management
- Implement destroy() for objects with external resources
- Provide accurate size estimates for memory tracking
- Clear large data structures in reset() methods

## Troubleshooting Common Issues

### Objects Not Being Reused
- Check if get_key() generates consistent keys for similar parameters
- Verify reset() returns True and properly cleans object state
- Ensure validate() doesn't reject valid objects

### Memory Leaks
- Implement destroy() method for objects with external resources
- Clear large data structures in reset() method
- Check for circular references in managed objects

### Performance Issues
- Profile create(), reset(), and validate() methods
- Optimize key generation for common cases
- Consider caching expensive validation checks

This comprehensive guide should enable you to create efficient, robust factories for any object type in the adaptive memory pool system.
