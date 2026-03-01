"""Tests for ObjectFactory interface."""

import sys

import pytest

from smartpool.core.factory_interface import ObjectFactory


class ConcreteFactory(ObjectFactory):
    """A concrete implementation for testing purposes."""

    def create(self, *args, **kwargs):
        return "created"

    def reset(self, obj):
        return True

    def validate(self, obj):
        return True

    def get_key(self, *args, **kwargs):
        return "key"

    # We don't implement destroy or estimate_size to test the defaults


class IncompleteFactory(ObjectFactory):
    """An incomplete factory missing the 'create' method for testing."""

    # Missing the 'create' method
    def reset(self, obj):
        return True

    def validate(self, obj):
        return True

    def get_key(self, *args, **kwargs):
        return "key"


class TestObjectFactoryInterface:
    """Tests for the ObjectFactory interface."""

    def test_abstract_methods_must_be_implemented(self):
        """Test that instantiating a factory without all abstract methods fails."""
        with pytest.raises(TypeError):
            IncompleteFactory()  # pylint: disable=abstract-class-instantiated

    def test_concrete_factory_instantiation(self):
        """Test that a correctly implemented factory can be instantiated."""
        try:
            factory = ConcreteFactory()
            assert isinstance(factory, ObjectFactory)
        except TypeError:
            pytest.fail("ConcreteFactory should instantiate without a TypeError.")

    def test_default_destroy_method(self):
        """Test that the default destroy() method exists and does nothing."""
        factory = ConcreteFactory()
        try:
            factory.destroy("some_object")
            # No exception should be raised
        except Exception as e:  # pylint: disable=broad-exception-caught
            pytest.fail(f"Default destroy() method raised an exception: {e}")

    def test_default_estimate_size_method(self):
        """Test the default estimate_size() method uses sys.getsizeof."""
        factory = ConcreteFactory()
        test_string = "hello world"

        # The default implementation should be equivalent to sys.getsizeof
        expected_size = sys.getsizeof(test_string)
        assert factory.estimate_size(test_string) == expected_size
