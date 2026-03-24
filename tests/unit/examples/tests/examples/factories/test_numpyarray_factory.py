"""Tests for NumpyArrayFactory."""

from unittest.mock import Mock, PropertyMock

import numpy as np
import pytest

from examples.factories import NumpyArrayFactory
from smartpool.core.exceptions import FactoryCreationError, FactoryKeyGenerationError


class TestNumpyArrayFactory:  # pylint: disable=attribute-defined-outside-init
    """Tests for NumpyArrayFactory."""

    def setup_method(self, method):  # pylint: disable=unused-argument
        """Set up test fixtures."""
        self.factory = NumpyArrayFactory()

    def test_create(self):
        """Test creating a numpy array."""
        shape = (10, 20)
        dtype = "uint8"
        array = self.factory.create(shape=shape, dtype=dtype)

        assert isinstance(array, np.ndarray)
        assert array.shape == shape
        assert array.dtype == np.dtype(dtype)
        assert np.all(array == 0)  # Should be initialized to zeros

        shape = (20, 30)
        dtype = "float32"
        array = self.factory.create(shape, dtype)

        assert isinstance(array, np.ndarray)
        assert array.shape == shape
        assert array.dtype == np.dtype(dtype)
        assert np.all(array == 0)  # Should be initialized to zeros

        with pytest.raises(FactoryCreationError):
            _ = self.factory.create(None, dtype)

    def test_validate(self):
        """Test the validation of a numpy array."""
        array = self.factory.create(shape=(5, 5))
        assert self.factory.validate(array)

        # Test with a non-writeable array
        array.flags.writeable = False
        assert not self.factory.validate(array)
        array.flags.writeable = True  # Reset for other tests

        # Test with a view of an array
        view = array[1:3, 1:3]
        assert not self.factory.validate(view)

        # Test with false class np.ndarray
        mock_array = Mock()
        mock_array.__class__ = np.ndarray
        mock_array.base = None
        mock_array.flags = None
        assert self.factory.validate(mock_array) is False

    def test_reset(self):
        """Test that the array is correctly reset to all zeros."""
        array = self.factory.create(shape=(3, 3))
        array.fill(42)  # Fill with a non-zero value
        assert not np.all(array == 0)

        assert self.factory.reset(array)
        assert np.all(array == 0)

    def test_get_key(self):
        """Test the key generation logic."""
        shape1 = (10, 10)
        dtype1 = "float32"
        key1 = self.factory.get_key(shape=shape1, dtype=dtype1)
        assert key1 == "numpy_(10, 10)_float32"

        shape2 = (20, 30)
        dtype2 = "int64"
        key2 = self.factory.get_key(shape=shape2, dtype=dtype2)
        assert key2 == "numpy_(20, 30)_int64"

        shape3 = (30, 30)
        dtype3 = "int8"
        key3 = self.factory.get_key(shape3, dtype=dtype3)
        assert key3 == "numpy_(30, 30)_int8"

        # shape is none
        with pytest.raises(FactoryKeyGenerationError):
            _ = self.factory.get_key(None, dtype3)

    def test_estimate_size(self):
        """Test the size estimation of the array."""
        shape = (10, 10)
        dtype = "float64"  # 8 bytes
        array = self.factory.create(shape=shape, dtype=dtype)

        expected_size = 10 * 10 * 8
        assert self.factory.estimate_size(array) == expected_size
        assert array.nbytes == expected_size

    def test_reset_exception(self):
        """Test that reset() handles exceptions gracefully."""
        mock_array = Mock()
        mock_array.fill.side_effect = AttributeError("Fill failed")
        assert not self.factory.reset(mock_array)

    def test_validate_exception(self):
        """Test that validate() handles exceptions gracefully."""
        mock_array = Mock(spec=np.ndarray)  # Mock a numpy array
        type(mock_array).base = PropertyMock(side_effect=AttributeError("Base access failed"))
        assert not self.factory.validate(mock_array)
