"""
Base test class for thumbnail factories to reduce code duplication.
"""

from unittest.mock import Mock


class BaseThumbnailFactoryTest:  # pylint: disable=too-few-public-methods, W0201
    """Base class for thumbnail factory tests, providing common setup."""

    def setup_method(self):
        """Setup mocks for each test."""
        self.format_handlers = {".jpg": Mock(), ".png": Mock(), ".gif": Mock()}
        self.pil_generator = Mock()
        self.placeholder_generator = Mock()
        self.logger = Mock()
        self.factory = None  # To be set by inheriting classes

    def test_get_key_different_parameters(self):
        """Test key generation with different parameters."""
        image_path = "/test/image.png"

        key1 = self.factory.get_key(image_path, (100, 100), 0.9)
        key2 = self.factory.get_key(image_path, (200, 150), 0.9)
        key3 = self.factory.get_key(image_path, (100, 100), 0.7)

        assert key1 != key2  # Different sizes
        assert key1 != key3  # Different quality factors
