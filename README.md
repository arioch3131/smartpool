# SmartPool - Intelligent Memory Pool

A highly modular and extensible generic memory pool for efficient object reuse in Python applications.

## Important Notice

**This is a personal project.** While the code is provided as-is and functional, please note:
- There will be **limited to no ongoing maintenance** of this project
- You are **free to fork** this repository and adapt it to your needs
- All usage must comply with the **MIT license** (see [LICENSE](LICENSE))

Feel free to use, modify, and distribute this code according to the license terms. Contributions are welcome but not guaranteed to be reviewed or merged.

## Overview

SmartPool is a modular memory pool system designed to improve object reuse and reduce allocation overhead in Python applications. It provides configurable pooling, monitoring, and presets for different workloads.

It is best suited for advanced or high-throughput scenarios with expensive objects and concurrency. For simple scripts, this is usually unnecessary overhead.

## Features

- **Zero Dependencies**: No external dependencies required for core functionality
- **Adaptive Management**: Automatic pool optimization based on usage patterns
- **Configuration Presets**: Pre-configured setups for common scenarios (web apps, image processing, databases, etc.)
- **Performance Monitoring**: Built-in metrics and statistics tracking
- **Thread-Safe**: Full concurrency support
- **Extensible**: Modular factory system for custom object types
- **Memory Efficient**: Automatic cleanup and memory pressure handling

## When Should You Use This?

### ✅ **Perfect For:**
- **High-throughput applications** with expensive-to-create objects
- **Concurrent systems** with 20+ simultaneous threads
- **Long-running services** where object reuse provides significant benefits
- Applications processing **large datasets** (images, files, network resources)
- Systems requiring **detailed performance monitoring** and automatic optimization
- **Enterprise applications** with complex object lifecycle management

### ❌ **Probably Overkill For:**
- Simple scripts or small applications
- Cases where objects are cheap to create (basic data structures)
- Single-threaded applications with low object churn
- Prototypes or development scripts

### 🤔 **Rule of Thumb:**
If you're creating hundreds of expensive objects per minute in a multi-threaded environment, this library will likely provide significant performance benefits. For simpler use cases, Python's built-in `functools.lru_cache` or a basic dictionary might be more appropriate.

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/arioch3131/smartpool.git
cd smartpool

# Install in development mode
pip install -e .

# Or install with optional dependencies
pip install -e ".[all]"  # All optional dependencies
pip install -e ".[dev]"  # Development dependencies
```

### Available Optional Dependencies

- `imaging`: Image processing support (`Pillow>=9.0.0`)
- `qt`: Qt GUI support (`PyQt6>=6.0.0`)
- `scientific`: Scientific computing (`numpy>=1.20.0`)
- `database`: Database support (`SQLAlchemy>=1.4.0`)
- `all`: All optional dependencies
- `dev`: Development tools (pytest, ruff, mypy, sphinx, etc.)

## Building a Wheel

To create a wheel distribution:

```bash
# Install build dependencies
pip install build

# Build the wheel
python -m build

# The wheel will be created in dist/
ls dist/
# smartpool-1.0.0-py3-none-any.whl
# smartpool-1.0.0.tar.gz
```

### Install the wheel

```bash
pip install dist/smartpool-1.0.0-py3-none-any.whl
```

## Quick Start

```python
from typing import Any

from smartpool import MemoryPreset, ObjectFactory, SmartObjectManager


class ByteArrayFactory(ObjectFactory[bytearray]):
    def create(self, *args: Any, **kwargs: Any) -> bytearray:
        size = args[0] if args and isinstance(args[0], int) else kwargs.get("size", 0)
        return bytearray(size)

    def reset(self, obj: bytearray) -> bool:
        obj.clear()
        return True

    def validate(self, obj: bytearray) -> bool:
        return isinstance(obj, bytearray)

    def get_key(self, *args: Any, **kwargs: Any) -> str:
        size = args[0] if args and isinstance(args[0], int) else kwargs.get("size", 0)
        bucket = (int(size) // 1024) * 1024
        return f"bytearray_{bucket}"

# Create a pool with high-throughput preset
factory = ByteArrayFactory()
pool = SmartObjectManager(factory, preset=MemoryPreset.HIGH_THROUGHPUT)

# Use the pool with context manager (recommended)
with pool.acquire_context(1024) as buffer:
    buffer.extend(b"Hello, World!")
    # buffer is automatically returned to the pool

# Clean shutdown
pool.shutdown()
```

## Documentation

📚 **Build the documentation locally**:

```bash
# From project root
bash scripts/build_docs.sh

# Or directly via Sphinx
cd docs
make html
```

The generated HTML is available in `docs/_build/html`.

### Key Documentation Sections:
- **API Reference**: Complete API documentation
- **Configuration Guide**: Detailed configuration options and presets
- **Factory Development**: How to create custom object factories
- **Performance Tuning**: Optimization tips and best practices
- **Architecture Overview**: Internal design and components

## Examples

The `examples/` directory contains comprehensive usage examples demonstrating various aspects of the adaptive memory pool system.

### Installing Example Dependencies

The examples require additional dependencies that are not included in the core package:

```bash
# Install all example dependencies
pip install -e ".[examples]"

# This includes:
# - uvicorn>=0.33.0 (ASGI server)
# - fastapi>=0.116.1 (Web framework)
# - Flask>=3.0.0 (Web framework)
# - numpy>=1.20.0 (Scientific computing)
# - SQLAlchemy>=1.4.0 (Database ORM)
# - Pillow>=9.0.0 (Image processing)
# - psutil>=7.0.0 (System monitoring)
# - requests>=2.0.0 (HTTP client)

# Or install individual dependencies as needed:
pip install -e ".[scientific]"  # For NumPy examples
pip install -e ".[imaging]"     # For image processing examples
pip install -e ".[database]"    # For database examples
```

### Running Examples

```bash
# Run basic examples
python examples/example_01_basic_bytesio.py
python examples/example_04_numpy_arrays.py
python examples/example_05_advanced_features.py

# Run specialized examples
python examples/example_02_pil_images.py
python examples/example_03_database_pool.py
python examples/example_06_custom_factory.py
python examples/example_07_main_web_server.py --framework fastapi
python examples/example_10_complete_integration.py
```

### Example Categories

#### 1. Foundation Examples

| File | Dependencies | Description |
|------|-------------|-------------|
| **example_01_basic_bytesio.py** | Core only | Simple pool creation, context managers, basic operations |
| **example_06_custom_factory.py** | Core only | Creating custom factories and object grouping logic |

#### 2. Monitoring & Performance

| File | Dependencies | Description |
|------|-------------|-------------|
| **example_09_debugging_troubleshooting.py** | `psutil` | Performance tracking, diagnostics and troubleshooting |
| **example_05_advanced_features.py** | Core only | Auto-optimization, background cleanup, complex scenarios |

#### 3. Scientific Computing

| File | Dependencies | Description |
|------|-------------|-------------|
| **example_04_numpy_arrays.py** | `numpy>=1.20.0` | NumPy array management for ML/scientific computing |

#### 4. Web Integration

| File | Dependencies | Description |
|------|-------------|-------------|
| **example_07_web_integration.py** | `Flask>=3.0.0, fastapi>=0.116.1, uvicorn>=0.33.0` | Flask & FastAPI integration patterns |
| **example_07_web_integration2.py** | `FastAPI, uvicorn` | Advanced web server patterns, realistic load testing |

#### 5. Image Processing

| File | Dependencies | Description |
|------|-------------|-------------|
| **example_02_pil_images.py** | `Pillow>=9.0.0` | PIL/Pillow image pools, thumbnail generation |

#### 6. Database Integration

| File | Dependencies | Description |
|------|-------------|-------------|
| **example_03_database_pool.py** | `SQLAlchemy>=1.4.0` | Database session pools, transaction management |

#### 7. Complete Applications

| File | Dependencies | Description |
|------|-------------|-------------|
| **example_10_complete_integration.py** | `[examples]` (all) | Full-featured application demonstrating all concepts |
| **example_08_advanced_patterns.py** | Core only | Advanced patterns, hierarchies and observability |

### Specialized Use Cases

#### Performance Testing & Benchmarking
- **example_09_debugging_troubleshooting.py**: Debug tools, memory leak detection, performance analysis
- **Load testing examples**: Realistic scenarios with concurrent operations

#### Custom Development
- **example_06_custom_factory.py**: Creating custom object factories for specific use cases
- **example_08_advanced_patterns.py**: Advanced design patterns, hierarchies, observability

### Example Dependencies by Category

```bash
# Web development examples
pip install "Flask>=3.0.0" "fastapi>=0.116.1" "uvicorn>=0.33.0"

# Scientific computing examples
pip install "numpy>=1.20.0"

# Image processing examples
pip install "Pillow>=9.0.0"

# Database examples
pip install "SQLAlchemy>=1.4.0"

# System monitoring examples
pip install "psutil>=7.0.0"

# HTTP client examples
pip install "requests>=2.0.0"
```

### Getting Started Guide

1. **Start with basics**: Run `examples/example_01_basic_bytesio.py` to understand core concepts
2. **Explore specialized factories**: Try `examples/example_02_pil_images.py` or `examples/example_04_numpy_arrays.py`
3. **Explore custom factories**: Use `examples/example_06_custom_factory.py` for extension patterns
4. **Add diagnostics**: Run `examples/example_09_debugging_troubleshooting.py` for performance insights
5. **Try your use case**: Choose specialized examples matching your needs

### Example Features Demonstrated

- ✅ **Basic Operations**: Pool creation, object acquisition, context managers
- ✅ **Configuration**: Presets, custom settings, auto-optimization
- ✅ **Monitoring**: Performance metrics, health checks, diagnostics
- ✅ **Web Integration**: Flask/FastAPI patterns, concurrent requests
- ✅ **Scientific Computing**: NumPy arrays, ML workflows, large data
- ✅ **Image Processing**: PIL/Pillow integration, thumbnail caching
- ✅ **Database Integration**: SQLAlchemy sessions, connection pooling
- ✅ **Production Deployment**: Environment configuration, monitoring
- ✅ **Custom Development**: Factory creation, advanced patterns

### Usage Guide
📖 **Comprehensive Guide**: See `examples/example_index_guide.md` for detailed explanations, use case recommendations, and troubleshooting tips.

### Performance Testing

Many examples include built-in performance testing and benchmarking capabilities:

```bash
# Most examples include timing and metrics
python examples/example_04_numpy_arrays.py      # Shows ML performance gains
python examples/example_07_web_client_tester.py # Web server throughput testing
```

### Troubleshooting Examples

If an example fails to run:

1. **Check dependencies**: Ensure the required optional dependencies are installed
2. **Python version**: Verify Python 3.11+ compatibility
3. **Environment**: Some examples may require specific system resources
4. **Documentation**: Refer to the example's docstring for specific requirements


## Running Tests

### Prerequisites

Install development dependencies:

```bash
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage (overrides default addopts if needed)
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/core/tests/core/test_smartpool_manager.py

# Run with verbose output
pytest -v

# Run tests in parallel (if pytest-xdist is installed)
pytest -n auto
```

### Test Categories:

- `tests/unit/core/tests/core/test_smartpool_manager.py`: Core pool functionality
- `tests/unit/core/tests/core/managers/`: Memory management features
- `tests/unit/examples/tests/examples/factories/`: Factory implementations
- `tests/unit/core/tests/core/test_config.py`: Configuration system
- `tests/unit/core/tests/core/metrics/`: Metrics and monitoring
- `tests/integration/`: Integration tests

### Coverage Report

After running tests with coverage, open `htmlcov/index.html` in your browser to see detailed coverage information.

### Test Configuration

Tests are configured via `pyproject.toml`:
- Test discovery patterns
- Coverage settings
- Pytest options

## Project Structure

```
smartpool/
├── src/smartpool/    # Main package
│   ├── core/                    # Core functionality
│   └── config.py                # Configuration models and presets
├── examples/factories/          # Example factory implementations
├── tests/                       # Test suite
├── examples/                    # Usage examples
├── docs/                        # Documentation
├── LICENSE                      # MIT License
├── pyproject.toml              # Project configuration
└── README.md                   # This file
```

## License

This project is licensed under the **MIT License**.

### What this means:
- ✅ **Share**: Copy and redistribute the material
- ✅ **Adapt**: Remix, transform, and build upon the material
- ✅ **Commercial Use**: Can be used in commercial and private contexts
- ✅ **Modification**: Can be modified and redistributed
- 📝 **Attribution**: Include the license and copyright notice

See the [LICENSE](LICENSE) file for complete terms.

## Requirements

- **Python**: 3.11+
- **Core Dependencies**: None (zero dependencies!)
- **Optional Dependencies**: See installation section above

## Acknowledgments

This project provides a comprehensive memory pool implementation designed for Python applications requiring efficient object reuse and memory management.
