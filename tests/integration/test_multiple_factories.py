"""
Integration tests for SmartObjectManager with multiple factory types.
These tests ensure that different factory implementations work correctly with the pool.
"""

from io import BytesIO

import pytest
from sqlalchemy import text

from examples.factories import BytesIOFactory, MetadataFactory
from smartpool import SmartObjectManager
from smartpool.config import MemoryConfig, PoolConfiguration

# Optional imports for factories
try:
    import numpy as np

    from examples.factories import NumpyArrayFactory

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from PIL import Image

    from examples.factories import PILImageFactory

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from examples.factories import SQLAlchemySessionFactory

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


class TestMultipleFactories:
    """
    Integration tests for SmartObjectManager with different factory types.
    """

    def test_bytesio_factory_integration(self):
        """
        Test complete integration with BytesIOFactory.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(max_objects_per_key=3, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Test object creation and usage
            obj_id, key, obj = pool.acquire()
            assert isinstance(obj, BytesIO)
            assert obj.tell() == 0  # Should be at beginning

            # Use the object
            test_data = b"Hello, World!"
            obj.write(test_data)
            assert obj.getvalue() == test_data

            # Release and verify reset
            pool.release(obj_id, key, obj)

            # Acquire again - should get reset object
            obj_id2, key2, obj2 = pool.acquire()
            assert obj2.getvalue() == b""  # Should be reset
            assert obj2.tell() == 0

            pool.release(obj_id2, key2, obj2)

            # Verify statistics
            stats = pool.get_basic_stats()
            assert stats["total_pooled_objects"] == 1
            assert stats["counters"]["creates"] >= 1
            assert stats["counters"]["hits"] >= 1

        finally:
            pool.shutdown()

    def test_metadata_factory_integration(self):
        """
        Test complete integration with MetadataFactory.
        """
        factory = MetadataFactory()
        config = MemoryConfig(max_objects_per_key=3, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Test object creation and usage
            obj_id, key, obj = pool.acquire()
            assert isinstance(obj, dict)
            assert len(obj) == 0  # Should start empty

            # Use the object
            obj["test_key"] = "test_value"
            obj["count"] = 42
            assert obj["test_key"] == "test_value"

            # Release and verify reset
            pool.release(obj_id, key, obj)

            # Acquire again - should get reset object
            obj_id2, key2, obj2 = pool.acquire()
            assert len(obj2) == 2  # Should preserve data (metadata cache behavior)
            assert obj2["test_key"] == "test_value"
            assert obj2["count"] == 42

            pool.release(obj_id2, key2, obj2)

            # Verify statistics
            stats = pool.get_basic_stats()
            assert stats["total_pooled_objects"] == 1

        finally:
            pool.shutdown()

    @pytest.mark.skipif(not NUMPY_AVAILABLE, reason="NumPy not available")
    def test_numpy_factory_integration(self):
        """
        Test complete integration with NumpyArrayFactory.
        """
        factory = NumpyArrayFactory()
        config = MemoryConfig(max_objects_per_key=2, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Test object creation and usage
            obj_id, key, obj = pool.acquire(shape=(100, 100), dtype=np.float32)
            assert isinstance(obj, np.ndarray)
            assert obj.shape == (100, 100)
            assert obj.dtype == np.float32
            assert np.all(obj == 0)  # Should be zeros

            # Use the object
            obj[0, 0] = 1.5
            obj[50, 50] = 2.5
            assert obj[0, 0] == 1.5
            assert obj[50, 50] == 2.5

            # Release and verify reset
            pool.release(obj_id, key, obj)

            # Acquire again - should get reset object
            obj_id2, key2, obj2 = pool.acquire(shape=(100, 100), dtype=np.float32)
            assert np.all(obj2 == 0)  # Should be reset to zeros

            pool.release(obj_id2, key2, obj2)

            # Test memory efficiency - should reuse same array
            assert id(obj) == id(obj2)  # Same underlying object

            # Verify statistics
            stats = pool.get_basic_stats()
            print(stats)
            assert stats["total_pooled_objects"] == 1
            assert stats["total_memory_bytes"] > 0

        finally:
            pool.shutdown()

    @pytest.mark.skipif(not PIL_AVAILABLE, reason="PIL not available")
    def test_pil_factory_integration(self):
        """
        Test complete integration with PILImageFactory.
        """
        factory = PILImageFactory()
        config = MemoryConfig(max_objects_per_key=2, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Test object creation and usage
            obj_id, key, obj = pool.acquire(width=200, height=200, mode="RGB")
            assert isinstance(obj, Image.Image)
            assert obj.size == (200, 200)
            assert obj.mode == "RGB"

            # Use the object
            # Draw a red pixel
            obj.putpixel((0, 0), (255, 0, 0))
            assert obj.getpixel((0, 0)) == (255, 0, 0)

            # Release and verify reset
            pool.release(obj_id, key, obj)

            # Acquire again - should get reset object
            obj_id2, key2, obj2 = pool.acquire(width=200, height=200, mode="RGB")
            # Should be reset (black image)
            assert obj2.getpixel((0, 0)) == (0, 0, 0)

            pool.release(obj_id2, key2, obj2)

            # Verify statistics
            stats = pool.get_basic_stats()
            assert stats["total_pooled_objects"] == 1

        finally:
            pool.shutdown()

    @pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="SQLAlchemy not available")
    def test_sqlalchemy_factory_integration(self):
        """
        Test complete integration with SQLAlchemySessionFactory.
        """
        # Use in-memory SQLite for testing
        engine = create_engine("sqlite:///:memory:", echo=False)

        factory = SQLAlchemySessionFactory(sessionmaker(bind=engine))
        config = MemoryConfig(max_objects_per_key=2, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Test object creation and usage
            obj_id, key, session = pool.acquire()
            assert session is not None
            assert hasattr(session, "execute")  # Should be a SQLAlchemy session

            # Use the session (basic query)
            result = session.execute(text("SELECT 1 as test_value"))
            row = result.fetchone()
            assert row[0] == 1

            # Release the session
            pool.release(obj_id, key, session)

            # Acquire again - should get a clean session
            obj_id2, key2, session2 = pool.acquire()
            assert session2 is not None

            pool.release(obj_id2, key2, session2)

            # Verify statistics
            stats = pool.get_basic_stats()
            assert stats["total_pooled_objects"] == 1

        finally:
            pool.shutdown()

    def test_multiple_factory_types_concurrently(self):
        """
        Test using multiple factory types in separate pools concurrently.
        """
        # Create pools with different factories
        bytesio_factory = BytesIOFactory()
        metadata_factory = MetadataFactory()

        config = MemoryConfig(max_objects_per_key=2, ttl_seconds=60)

        bytesio_pool = SmartObjectManager(
            factory=bytesio_factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        metadata_pool = SmartObjectManager(
            factory=metadata_factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Use both pools simultaneously
            bio_obj_id, bio_key, bio_obj = bytesio_pool.acquire()
            meta_obj_id, meta_key, meta_obj = metadata_pool.acquire()

            # Verify correct types
            assert isinstance(bio_obj, BytesIO)
            assert isinstance(meta_obj, dict)

            # Use both objects
            bio_obj.write(b"test data")
            meta_obj["test"] = "value"

            # Verify independent operation
            assert bio_obj.getvalue() == b"test data"
            assert meta_obj["test"] == "value"

            # Release both
            bytesio_pool.release(bio_obj_id, bio_key, bio_obj)
            metadata_pool.release(meta_obj_id, meta_key, meta_obj)

            # Verify independent statistics
            bio_stats = bytesio_pool.get_basic_stats()
            meta_stats = metadata_pool.get_basic_stats()

            assert bio_stats["total_pooled_objects"] == 1
            assert meta_stats["total_pooled_objects"] == 1

        finally:
            bytesio_pool.shutdown()
            metadata_pool.shutdown()

    def test_factory_validation_and_reset_integration(self):
        """
        Test that factory validation and reset methods work correctly.
        """
        factory = BytesIOFactory()
        config = MemoryConfig(max_objects_per_key=2, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Acquire and modify object
            obj_id, key, obj = pool.acquire()
            obj.write(b"test data")
            assert obj.getvalue() == b"test data"

            # Object should be valid
            assert factory.validate(obj) is True

            # Release - should reset the object
            pool.release(obj_id, key, obj)

            # Acquire again - should get reset object
            obj_id2, key2, obj2 = pool.acquire()
            assert obj2.getvalue() == b""  # Reset to empty
            assert factory.validate(obj2) is True

            pool.release(obj_id2, key2, obj2)

        finally:
            pool.shutdown()

    def test_factory_size_estimation(self):
        """
        Test that factory size estimation works correctly.
        """
        factory = MetadataFactory()
        config = MemoryConfig(max_objects_per_key=2, ttl_seconds=60)
        pool = SmartObjectManager(
            factory=factory,
            default_config=config,
            pool_config=PoolConfiguration(register_atexit=False),
        )

        try:
            # Acquire object and check size estimation
            obj_id, key, obj = pool.acquire()

            # Empty dict should have minimal size
            empty_size = factory.estimate_size(obj)
            assert empty_size > 0

            # Add data and check size increases
            obj["key1"] = "value1" * 100  # Add significant data
            obj["key2"] = list(range(100))

            filled_size = factory.estimate_size(obj)
            assert filled_size > empty_size

            pool.release(obj_id, key, obj)

            # Check pool statistics include memory estimation
            stats = pool.get_basic_stats()
            assert "total_memory_bytes" in stats
            assert stats["total_memory_bytes"] > 0

        finally:
            pool.shutdown()
