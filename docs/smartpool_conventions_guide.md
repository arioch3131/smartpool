# SmartPool Coding Conventions Guide

## Overview

This document establishes the coding conventions and style guidelines for the SmartPool project. Following these conventions ensures consistency, maintainability, and clarity across the codebase.

## General Principles

### Language Requirements
- **English Only**: All code, comments, documentation, and identifiers must be in English
- **No Internationalization**: No support for multiple languages in code elements
- **ASCII Characters**: Use only ASCII characters in identifiers

### Code Organization
- **Modular Architecture**: Separate concerns into specialized manager classes
- **Single Responsibility**: Each class and method should have one clear purpose
- **Dependency Injection**: Use dependency injection for testability and flexibility

## Naming Conventions

### General Rules
- **snake_case**: All identifiers (variables, functions, methods, modules)
- **PascalCase**: Class names and type aliases
- **SCREAMING_SNAKE_CASE**: Constants and enum values
- **Descriptive Names**: Names should clearly indicate purpose and functionality

### Specific Patterns

#### Class Names
```python
# Core managers
class SmartObjectManager:          # Main orchestrator
class ActiveObjectsManager:        # Specific responsibility
class PoolOperationsManager:       # Action-oriented
class BackgroundManager:           # Domain-specific

# Factories
class BytesIOFactory:              # Type + Factory suffix
class DatabaseFactory:             # Domain + Factory suffix
class CustomImageFactory:          # Descriptive + Factory suffix

# Data models
class PooledObject:                # Past participle + Object
class MemoryConfig:                # Domain + Config suffix
class PerformanceMetrics:          # Domain + Metrics suffix
```

#### Method Names
```python
# Lifecycle methods
def create(self, *args, **kwargs):     # Core factory operations
def reset(self, obj):
def validate(self, obj):
def destroy(self, obj):

# Acquisition patterns
def acquire(self, *args, **kwargs):    # Main operations
def release(self, obj_id, key, obj):
def acquire_context(self, *args):      # Context manager variant

# Information retrieval
def get_basic_stats(self):             # get_ prefix for retrieval
def get_detailed_stats(self):
def get_key(self, *args, **kwargs):    # Key generation

# State management
def should_add_to_pool(self, ...):     # Boolean questions with should_
def is_valid(self):                    # Boolean state with is_
def can_acquire(self):                 # Capability check with can_

# Estimation and calculation
def estimate_size(self, obj):          # estimate_ for approximations
def calculate_hit_rate(self):          # calculate_ for precise computations
```

#### Attribute Names
```python
# Configuration attributes
max_objects_per_key: int              # max_ prefix for limits
ttl_seconds: float                    # _seconds suffix for time
enable_logging: bool                  # enable_ prefix for toggles
cleanup_interval_seconds: float       # descriptive with units

# State tracking
created_at: float                     # timestamp with _at suffix
last_accessed: float                  # temporal with last_ prefix
access_count: int                     # count suffix for counters
validation_failures: int             # failures suffix for error counts

# Collections and managers
active_objects_count: Dict                  # descriptive plural for collections
pool: Dict[str, Deque]               # domain-specific container names
operations_manager: PoolOperationsManager  # manager suffix for dependencies
```

## Architecture Patterns

### Manager Classes
- **Suffix**: All manager classes end with `Manager`
- **Responsibility**: Each manager handles one specific aspect
- **Injection**: Managers are injected into the main orchestrator

```python
class SmartObjectManager:
    def __init__(self, factory, ...):
        self.active_manager = ActiveObjectsManager()
        self.operations_manager = PoolOperationsManager()
        self.background_manager = BackgroundManager()
```

### Factory Interface
- **Inheritance**: All factories inherit from `ObjectFactory[T]`
- **Required Methods**: `create`, `reset`, `validate`, `get_key`
- **Optional Methods**: `destroy`, `estimate_size`

### Configuration Objects
- **Dataclasses**: Use `@dataclass` for configuration objects
- **Typing**: Full type annotations for all attributes
- **Defaults**: Sensible defaults for optional parameters

## Documentation Standards

### Docstring Format
```python
def method_name(self, param: Type) -> ReturnType:
    """
    Brief description of what the method does.
    
    Longer description if needed, explaining the behavior,
    use cases, and any important details.
    
    Args:
        param (Type): Description of the parameter.
        
    Returns:
        ReturnType: Description of what is returned.
        
    Raises:
        ExceptionType: When this exception is raised.
    """
```

### Comment Style
- **Purpose**: Explain why, not what
- **Complex Logic**: Comment non-obvious algorithms
- **TODOs**: Use `# TODO:` for future improvements
- **Performance Notes**: Document performance considerations

## Error Handling

### Exception Hierarchy
```python
# Base exceptions
class SmartPoolError(Exception):          # Base for all pool errors
class ObjectAcquisitionError(SmartPoolError):  # Specific operation errors
class ObjectStateCorruptedError(SmartPoolError):
class PoolAlreadyShutdownError(SmartPoolError):
```

### Exception Handling Patterns
```python
# Specific exception types for different error categories
try:
    operation()
except ConnectionError as exc:
    # Network-related errors
    safe_log(logger, logging.WARNING, f"Network error: {exc}")
except (AttributeError, ValueError, TypeError) as exc:
    # Object state errors
    safe_log(logger, logging.WARNING, f"Object error: {exc}")
except (MemoryError, BufferError) as exc:
    # Memory-related errors
    safe_log(logger, logging.ERROR, f"Memory error: {exc}")
```

## Type Annotations

### Required Annotations
- **All public methods**: Full type annotations required
- **All attributes**: Type hints in class definitions
- **Generic types**: Use `TypeVar` for generic classes

```python
from typing import Generic, TypeVar, Optional, Dict, Any

T = TypeVar("T")

class SmartObjectManager(Generic[T]):
    def __init__(
        self,
        factory: ObjectFactory[T],
        default_config: Optional[MemoryConfig] = None,
    ) -> None:
```

### Import Organization
```python
# Standard library imports
import logging
import threading
from typing import Any, Dict, Generic, Optional, TypeVar

# Third-party imports
import numpy as np

# Local imports
from smartpool.core.exceptions import SmartPoolError
from smartpool.core.factory_interface import ObjectFactory
```

## Testing Conventions

### Test Class Names
```python
class TestSmartObjectManagerOrchestration:    # Test + ClassName + Aspect
class TestFactoryInterface:                   # Test + ComponentName
class TestMemoryConfigValidation:             # Test + Class + Behavior
```

### Test Method Names
```python
def test_acquire_returns_valid_object(self):          # test_ + action + outcome
def test_release_with_invalid_id_raises_error(self):  # test_ + scenario + result
def test_background_cleanup_removes_expired(self):    # test_ + component + behavior
```

### Mock Names
```python
mock_factory = Mock()                         # mock_ prefix
mock_active_manager = Mock()                  # descriptive mock names
factory_mock = MockFactory()                  # component mock classes
```

## Performance Guidelines

### Memory Management
- **Resource Cleanup**: Always implement `destroy()` for external resources
- **Size Estimation**: Provide accurate `estimate_size()` implementations
- **Weak References**: Use weak references for tracking without retention

### Concurrency
- **Thread Safety**: All public methods must be thread-safe
- **Lock Granularity**: Use fine-grained locking when possible
- **Lock Naming**: Descriptive names for locks (`_pool_lock`, `_stats_lock`)

## Configuration Patterns

### Preset System
```python
class MemoryPreset:
    HIGH_THROUGHPUT = "high_throughput"       # Performance-focused
    LOW_MEMORY = "low_memory"                 # Resource-constrained
    DATABASE_CONNECTIONS = "database_connections"  # Use-case specific
    DEVELOPMENT = "development"               # Environment-specific
```

### Configuration Validation
- **Type Checking**: Validate configuration types
- **Range Checking**: Ensure numeric values are within valid ranges
- **Dependency Validation**: Check for conflicting settings

## Extension Guidelines

### Custom Factories
```python
class CustomFactory(ObjectFactory[CustomType]):
    """Factory for CustomType objects."""
    
    def create(self, *args, **kwargs) -> CustomType:
        """Creates a new CustomType instance."""
        
    def get_key(self, *args, **kwargs) -> str:
        """Generates key based on creation parameters."""
        # Group similar objects for efficient reuse
        return f"custom_{param_category}_{size_bucket}"
```

### Custom Managers
- **Interface Compliance**: Follow existing manager patterns
- **Dependency Injection**: Accept dependencies in constructor
- **Error Handling**: Use consistent error handling patterns

## Deprecation Process

### Marking Deprecations
```python
import warnings

def deprecated_method(self):
    """This method is deprecated."""
    warnings.warn(
        "deprecated_method is deprecated, use new_method instead",
        DeprecationWarning,
        stacklevel=2
    )
```

### Migration Path
- **Version Compatibility**: Maintain backward compatibility for at least one major version
- **Clear Documentation**: Provide clear migration instructions
- **Timeline**: Announce deprecation timeline in release notes

## Code Quality Tools

### Required Tools
- **Black**: Code formatting
- **isort**: Import sorting  
- **flake8**: Style checking
- **pylint**: Static analysis
- **mypy**: Type checking
- **pytest**: Testing framework

### Configuration Files
- **pyproject.toml**: Centralized tool configuration
- **Consistent Settings**: Ensure all tools use compatible settings
- **CI Integration**: Run all tools in continuous integration

## Release Process

### Version Numbering
- **Semantic Versioning**: Follow SemVer (MAJOR.MINOR.PATCH)
- **Development Versions**: Use `.devN` suffix for development releases
- **Release Candidates**: Use `rcN` suffix for release candidates

### Changelog Format
```markdown
## [1.2.0] - 2024-01-15

### Added
- New feature descriptions

### Changed  
- Behavior modifications

### Deprecated
- Features marked for removal

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security improvements
```

## Conclusion

These conventions ensure consistency and maintainability across the SmartPool codebase. When extending or modifying the code, always follow these guidelines to maintain the high quality and coherence of the project.

For questions about these conventions or proposed changes, please discuss with the development team before implementation.
