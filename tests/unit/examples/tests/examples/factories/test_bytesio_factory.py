"""Tests for BytesIOFactory."""

from io import BytesIO
from unittest.mock import Mock

import pytest

from examples.factories import BytesIOFactory


class TestBytesIOFactory:  # pylint: disable=attribute-defined-outside-init
    """Tests for BytesIOFactory."""

    def setup_method(self):
        """Set up test fixtures."""
        self.factory = BytesIOFactory()

    def test_create(self):
        """Test creating a BytesIO object."""
        buffer = self.factory.create()
        assert isinstance(buffer, BytesIO)
        assert buffer.writable()
        assert buffer.readable()
        assert buffer.seekable()

    def test_create_with_initial_size(self):
        """Test creating a BytesIO object with a pre-allocated size."""
        size = 1024
        buffer = self.factory.create(initial_size=size)
        assert buffer.getvalue() == b"\0" * size
        assert buffer.tell() == 0

        buffer = self.factory.create(size)
        assert buffer.getvalue() == b"\0" * size
        assert buffer.tell() == 0

    def test_validate(self):
        """Test the validation of a BytesIO object."""
        buffer = self.factory.create()
        assert self.factory.validate(buffer)

        buffer.close()
        assert not self.factory.validate(buffer)

    def test_reset(self):
        """Test that the buffer is correctly reset."""
        buffer = self.factory.create()
        buffer.write(b"some test data")
        assert buffer.tell() > 0

        assert self.factory.reset(buffer)
        assert buffer.tell() == 0
        assert buffer.getvalue() == b""

    def test_get_key(self):
        """Test the key generation logic."""
        assert self.factory.get_key(initial_size=0) == "bytesio_0"
        assert self.factory.get_key(initial_size=500) == "bytesio_0"
        assert self.factory.get_key(initial_size=1024) == "bytesio_1024"
        assert self.factory.get_key(initial_size=1500) == "bytesio_1024"
        assert self.factory.get_key(0) == "bytesio_0"
        assert self.factory.get_key(500) == "bytesio_0"
        assert self.factory.get_key(1024) == "bytesio_1024"
        assert self.factory.get_key(1500) == "bytesio_1024"

    def test_destroy(self):
        """Test that the destroy method closes the buffer."""
        buffer = self.factory.create()
        assert not buffer.closed
        self.factory.destroy(buffer)
        assert buffer.closed

    def test_estimate_size(self):
        """Test the size estimation of the buffer."""
        buffer = self.factory.create()
        buffer.write(b"12345")
        assert self.factory.estimate_size(buffer) == 5

        buffer.write(b"67890")
        assert self.factory.estimate_size(buffer) == 10

        # Check that it returns to original position
        buffer.seek(3)
        assert self.factory.estimate_size(buffer) == 10
        assert buffer.tell() == 3

    def test_reset_exception(self):
        """Test that reset() handles exceptions gracefully."""
        mock_buffer = Mock()
        mock_buffer.seek.side_effect = IOError("Seek failed")
        assert not self.factory.reset(mock_buffer)

    def test_destroy_exception(self):
        """Test that destroy() handles exceptions gracefully."""
        mock_buffer = Mock()
        mock_buffer.close.side_effect = IOError("Close failed")
        try:
            self.factory.destroy(mock_buffer)
        except Exception as e:  # pylint: disable=broad-exception-caught
            pytest.fail(f"destroy() should not raise exceptions, but raised {e}")

    def test_estimate_size_exception(self):
        """Test that estimate_size() handles exceptions gracefully."""
        mock_buffer = Mock()
        mock_buffer.tell.side_effect = IOError("Tell failed")
        assert self.factory.estimate_size(mock_buffer) == 0
