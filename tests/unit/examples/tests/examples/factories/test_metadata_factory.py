"""
Complete unit tests for MetadataFactory
"""

import time
from unittest.mock import MagicMock, patch

from examples.factories import MetadataDict, MetadataFactory


class CorruptedMetadataDict(MetadataDict):
    """Helper class for testing corrupted MetadataDict behavior."""

    # pylint: disable=too-few-public-methods
    def __len__(self):
        raise TypeError("Corrupted len() method")


class TestMetadataDict:
    """Tests for the MetadataDict class."""

    def test_init_empty(self):
        """Test creating an empty MetadataDict."""
        md = MetadataDict()
        assert len(md) == 0
        assert isinstance(md, dict)
        assert md._created_at is None  # pylint: disable=protected-access
        assert md._file_path is None  # pylint: disable=protected-access

    def test_init_with_data(self):
        """Test creating MetadataDict with initial data."""
        md = MetadataDict({"key": "value", "test": 123})
        assert len(md) == 2
        assert md["key"] == "value"
        assert md["test"] == 123

    def test_init_with_kwargs(self):
        """Test creating MetadataDict with kwargs."""
        md = MetadataDict(key="value", test=123)
        assert len(md) == 2
        assert md["key"] == "value"
        assert md["test"] == 123

    def test_set_metadata(self):
        """Test the set_metadata method."""
        md = MetadataDict()

        # Test without file_path
        md.set_metadata()
        assert md._created_at is not None  # pylint: disable=protected-access
        assert md._file_path is None  # pylint: disable=protected-access

        # Test with file_path
        test_path = "/test/path.jpg"
        md.set_metadata(test_path)
        assert md._file_path == test_path  # pylint: disable=protected-access
        assert md._created_at is not None  # pylint: disable=protected-access

    def test_repr(self):
        """Test the __repr__ method."""
        md = MetadataDict({"key": "value"})
        repr_str = repr(md)
        assert "MetadataDict" in repr_str
        assert "key" in repr_str
        assert "value" in repr_str

    def test_dict_functionality(self):
        """Test that MetadataDict works like a normal dict."""
        md = MetadataDict()
        md["test"] = "value"
        assert md["test"] == "value"
        assert "test" in md
        assert list(md.keys()) == ["test"]


class TestMetadataFactory:
    """Complete tests for MetadataFactory."""  # pylint: disable=too-many-public-methods

    def test_create(self):
        """Test creating a new object."""
        factory = MetadataFactory()
        result = factory.create("/test/path.jpg")
        assert isinstance(result, MetadataDict)
        assert len(result) == 0
        assert result._file_path == "/test/path.jpg"  # pylint: disable=protected-access
        assert result._created_at is not None  # pylint: disable=protected-access

    def test_create_with_args_kwargs(self):
        """Test creation with additional args and kwargs."""
        factory = MetadataFactory()
        result = factory.create("/test/path.jpg", "extra_arg", extra_kwarg="value")
        assert isinstance(result, MetadataDict)
        assert result._file_path == "/test/path.jpg"  # pylint: disable=protected-access
        result = factory.create(file_path="/test/path.jpg")
        assert isinstance(result, MetadataDict)
        assert result._file_path == "/test/path.jpg"  # pylint: disable=protected-access

    def test_reset_success(self):
        """Test successful reset."""
        factory = MetadataFactory()
        obj = factory.create("test_path")
        obj["key"] = "value"
        obj["another"] = "data"

        result = factory.reset(obj)
        assert result is True
        assert len(obj) == 2  # Data should be preserved

    def test_reset_corrupted_object(self):
        """Test reset with a corrupted object."""
        factory = MetadataFactory()

        # Create a real MetadataDict with a problem on len()
        corrupted_obj = CorruptedMetadataDict()
        result = factory.reset(corrupted_obj)
        assert result is False

    def test_reset_exception_handling(self):
        """Test exception handling in reset."""
        factory = MetadataFactory()

        # Mock that raises an exception from the start
        problematic_obj = MagicMock()
        problematic_obj.__class__ = Exception  # Force isinstance to fail

        # Create a real MetadataDict with a problem on len()
        corrupted_obj = CorruptedMetadataDict()
        result = factory.reset(corrupted_obj)
        assert result is False

    def test_validate_valid(self):
        """Test validation of valid objects."""
        factory = MetadataFactory()

        # Empty MetadataDict
        obj = factory.create("test_path")
        assert factory.validate(obj) is True

        # MetadataDict with data
        obj["key"] = "value"
        assert factory.validate(obj) is True

    def test_validate_corrupted_object(self):
        """Test validation of a corrupted object."""
        factory = MetadataFactory()

        # Create a real MetadataDict but with a problem on len()
        corrupted_obj = CorruptedMetadataDict()
        result = factory.validate(corrupted_obj)
        assert result is False

    def test_get_key_valid_paths(self):
        """Test key generation with valid paths."""
        factory = MetadataFactory()

        # Test path normalization
        key1 = factory.get_key("/path/to/file.jpg")
        key2 = factory.get_key("/path/to/../to/file.jpg")

        assert key1 == key2
        assert key1.startswith("metadata:")
        assert "file.jpg" in key1

    def test_get_key_invalid_paths(self):
        """Test key generation with invalid paths."""
        factory = MetadataFactory()

        assert factory.get_key("") == "invalid_path"
        assert factory.get_key(None) == "invalid_path"
        assert factory.get_key(123) == "invalid_path"

    def test_get_key_normalization_error(self):
        """Test error handling in path normalization."""
        factory = MetadataFactory()

        # Mock os.path.abspath to raise an exception
        with patch("os.path.abspath", side_effect=OSError("Path error")):
            result = factory.get_key("/some/path")
            assert result == "metadata:/some/path"  # Fallback

    def test_get_key_with_args_kwargs(self):
        """Test get_key with additional args and kwargs."""
        factory = MetadataFactory()
        result = factory.get_key("/test/path", "extra_arg", extra_kwarg="value")
        assert result.startswith("metadata:")

    def test_get_key_with_filepath(self):
        """Test get_key with additional args and kwargs."""
        factory = MetadataFactory()
        result = factory.get_key(file_path="/test/path")
        assert result.startswith("metadata:")

    def test_destroy_success(self):
        """Test successful destruction."""
        factory = MetadataFactory()
        obj = {"key": "value", "test": 123}

        factory.destroy(obj)
        assert len(obj) == 0

    def test_destroy_exception_handling(self):
        """Test exception handling in destroy."""
        factory = MetadataFactory()

        # Mock that raises an exception on clear()
        problematic_obj = MagicMock()
        problematic_obj.clear.side_effect = AttributeError("Clear failed")

        # Should not raise an exception # pylint: disable=broad-exception-caught
        factory.destroy(problematic_obj)

    def test_force_clear_success(self):
        """Test successful force_clear."""
        factory = MetadataFactory()
        obj = {"key": "value", "test": 123}

        result = factory.force_clear(obj)
        assert result is True
        assert len(obj) == 0

    def test_force_clear_failure(self):
        """Test force_clear with failure."""
        factory = MetadataFactory()

        # Mock that raises an exception on clear()
        problematic_obj = MagicMock()
        problematic_obj.clear.side_effect = AttributeError("Clear failed")

        result = factory.force_clear(problematic_obj)
        assert result is False

    def test_estimate_size_empty(self):
        """Test size estimation for an empty object."""
        factory = MetadataFactory()
        empty_dict = {}

        size = factory.estimate_size(empty_dict)
        assert size > 0

    def test_estimate_size_with_data(self):
        """Test size estimation with data."""
        factory = MetadataFactory()

        empty_dict = {}
        small_dict = {"key": "value"}
        large_dict = {"key" + str(i): f"value{i}" for i in range(10)}

        empty_size = factory.estimate_size(empty_dict)
        small_size = factory.estimate_size(small_dict)
        large_size = factory.estimate_size(large_dict)

        assert empty_size < small_size < large_size

    def test_estimate_size_exception_handling(self):
        """Test exception handling in estimate_size."""
        factory = MetadataFactory()

        # Test with an object that causes problems during iteration
        # but not in sys.getsizeof
        class ProblematicDict(dict):
            """Helper class for testing problematic dict iteration."""

            # pylint: disable=too-few-public-methods
            def items(self):
                raise TypeError("Iteration failed")

        problematic_obj = ProblematicDict({"test": "value"})

        # Should return a base estimate via fallback
        size = factory.estimate_size(problematic_obj)
        assert size > 0  # Fallback to sys.getsizeof(obj)

    def test_estimate_value_size_basic_types(self):
        """Test size estimation for basic types."""
        factory = MetadataFactory()

        # Test different types
        string_size = factory._estimate_value_size("test")  # pylint: disable=protected-access
        int_size = factory._estimate_value_size(123)  # pylint: disable=protected-access
        float_size = factory._estimate_value_size(3.14)  # pylint: disable=protected-access
        bool_size = factory._estimate_value_size(True)  # pylint: disable=protected-access

        assert all(size > 0 for size in [string_size, int_size, float_size, bool_size])

    def test_estimate_value_size_nested_dict(self):
        """Test size estimation for a nested dictionary."""
        factory = MetadataFactory()

        nested_dict = {"level1": {"level2": {"level3": "deep_value"}}}

        size = factory._estimate_value_size(nested_dict)  # pylint: disable=protected-access
        assert size > 0

    def test_estimate_value_size_list_tuple(self):
        """Test size estimation for lists and tuples."""
        factory = MetadataFactory()

        test_list = [1, "test", {"nested": "dict"}]
        test_tuple = (1, "test", {"nested": "dict"})

        list_size = factory._estimate_value_size(test_list)  # pylint: disable=protected-access
        tuple_size = factory._estimate_value_size(test_tuple)  # pylint: disable=protected-access

        assert list_size > 0
        assert tuple_size > 0

    def test_estimate_value_size_complex_nested(self):
        """Test estimation with complex nested structures."""
        factory = MetadataFactory()

        complex_data = {
            "lists": [1, 2, [3, 4, [5, 6]]],
            "dicts": {"a": {"b": {"c": "deep"}}},
            "mixed": [{"key": "value"}, ("tuple", "data")],
        }

        size = factory._estimate_value_size(complex_data)  # pylint: disable=protected-access
        assert size > 0

    def test_estimate_value_size_exception_handling(self):
        """Test exception handling in _estimate_value_size."""
        factory = MetadataFactory()

        # Create an object that raises an exception in sys.getsizeof
        class ProblematicObject:
            """Helper class for testing problematic object sizing."""

            # pylint: disable=too-few-public-methods
            def __sizeof__(self):
                raise TypeError("sizeof failed")

        problematic_obj = ProblematicObject()

        # Should return 100 (conservative estimate) # pylint: disable=broad-exception-caught
        size = factory._estimate_value_size(problematic_obj)  # pylint: disable=protected-access
        assert size == 100

    def test_estimate_size_none_object(self):
        """Test estimate_size with a None object."""
        factory = MetadataFactory()

        size = factory.estimate_size(None)
        assert size > 0  # Should return the size of an empty dict

    def test_estimate_size_with_none_values(self):
        """Test estimate_size with None values in the dict."""
        factory = MetadataFactory()

        dict_with_none = {"key": None, "another": "value"}
        size = factory.estimate_size(dict_with_none)
        assert size > 0

    def test_comprehensive_workflow(self):
        """Test complete workflow."""
        factory = MetadataFactory()

        # Create an object
        file_path = "/test/comprehensive/test.jpg"
        metadata = factory.create(file_path)

        # Validate
        assert factory.validate(metadata) is True

        # Add data
        metadata["analysis"] = {"confidence": 0.95, "tags": ["cat", "animal"]}
        metadata["timestamp"] = time.time()

        # Generate a key
        key = factory.get_key(file_path)
        assert key.startswith("metadata:")

        # Estimate size
        size = factory.estimate_size(metadata)
        assert size > 0

        # Reset (should preserve data)
        assert factory.reset(metadata) is True
        assert len(metadata) == 2

        # Force clear
        assert factory.force_clear(metadata) is True
        assert len(metadata) == 0

        # Destroy
        metadata["temp"] = "data"
        factory.destroy(metadata)
        assert len(metadata) == 0
