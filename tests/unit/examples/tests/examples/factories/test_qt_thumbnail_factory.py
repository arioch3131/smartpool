"""
Complete unit tests for QtThumbnailFactory - 100% coverage.
"""

# pylint: disable=W0201

from unittest.mock import Mock, patch

import pytest

from examples.factories import QtThumbnailFactory

from .base_thumbnail_test import BaseThumbnailFactoryTest


class TestQtThumbnailFactory(BaseThumbnailFactoryTest):  # pylint: disable=too-many-public-methods, W0201
    """Tests for QtThumbnailFactory."""

    def setup_method(self):  # pylint: disable=W0201
        """Setup for each test."""
        super().setup_method()

        # Create a real mocked QPixmap class to avoid isinstance issues
        class _MockQPixmap:
            """Mock QPixmap class for testing."""

            # pylint: disable=too-few-public-methods
            def __init__(self, is_null=False):
                """Initializes the mock QPixmap."""
                self._is_null = is_null
                self._width = 100
                self._height = 100
                self._depth = 24

            def is_null(self):
                """Returns if the pixmap is null."""
                return self._is_null

            def width(self):
                """Returns the width of the pixmap."""
                return self._width

            def height(self):
                """Returns the height of the pixmap."""
                return self._height

            def depth(self):
                """Returns the depth of the pixmap."""
                return self._depth

        self.mock_qpixmap_class = _MockQPixmap

        # Import assuming PyQt6 is available
        try:
            self.factory = QtThumbnailFactory(
                format_handlers=self.format_handlers,
                pil_generator=self.pil_generator,
                placeholder_generator=self.placeholder_generator,
                logger=self.logger,
            )
            self.qt_available = True

        except ImportError:
            self.qt_available = False
            self.factory = None

    def test_init(self):
        """Test the constructor."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        assert self.factory.format_handlers == self.format_handlers
        assert self.factory.pil_generator == self.pil_generator
        assert self.factory.placeholder_generator == self.placeholder_generator
        assert self.factory.logger == self.logger

    def test_get_key_basic(self):
        """Test basic key generation."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        result = self.factory.get_key("/path/image.jpg", (150, 150), 0.8)
        assert result == "/path/image.jpg_150x150_0.8"

    def test_create_with_handler(self):
        """Test creation with a specific handler."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        mock_qpixmap = self.mock_qpixmap_class()
        self.format_handlers[".jpg"].return_value = mock_qpixmap

        result = self.factory.create("/test/image.jpg", (100, 100), 0.8)

        assert result == mock_qpixmap
        self.format_handlers[".jpg"].assert_called_once_with("/test/image.jpg", (100, 100), 0.8)

    def test_create_with_pil_generator(self):
        """Test creation with the default pil_generator."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        mock_qpixmap = self.mock_qpixmap_class()
        self.pil_generator.generate.return_value = mock_qpixmap

        result = self.factory.create("/test/image.bmp", (100, 100), 0.8)

        assert result == mock_qpixmap
        self.pil_generator.generate.assert_called_once_with("/test/image.bmp", (100, 100), 0.8)

    def test_create_handler_returns_none(self):
        """Test fallback when handler returns None."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        self.format_handlers[".jpg"].return_value = None
        mock_placeholder = self.mock_qpixmap_class()
        self.placeholder_generator.generate.return_value = mock_placeholder

        result = self.factory.create("/test/image.jpg", (100, 100), 0.8)

        assert result == mock_placeholder
        self.logger.warning.assert_called_once()

    def test_create_handler_exception(self):
        """Test fallback on exception."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        self.format_handlers[".jpg"].side_effect = RuntimeError("Handler failed")
        mock_placeholder = self.mock_qpixmap_class()
        self.placeholder_generator.generate.return_value = mock_placeholder

        result = self.factory.create("/test/image.jpg", (100, 100), 0.8)

        assert result == mock_placeholder
        self.logger.error.assert_called_once()

    def test_create_case_insensitive_extensions(self):
        """Test case-insensitive extensions."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        mock_qpixmap = self.mock_qpixmap_class()
        self.format_handlers[".jpg"].return_value = mock_qpixmap

        result = self.factory.create("/test/image.JPG", (100, 100), 0.8)

        assert result == mock_qpixmap
        self.format_handlers[".jpg"].assert_called_once()

    def test_validate_valid_qpixmap(self):
        """Test validation with a valid QPixmap."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")
        # Use a mock directly with patch
        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = False  # pylint: disable=protected-access
        mock_qpixmap.width.return_value = 100
        mock_qpixmap.height.return_value = 100
        mock_qpixmap.depth.return_value = 24

        with patch("examples.factories.qt.qt_thumbnail_factory.isinstance", return_value=True):
            result = self.factory.validate(mock_qpixmap)
            assert result is True

    def test_validate_null_qpixmap(self):
        """Test validation of a null QPixmap."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        mock_qpixmap = Mock()
        mock_qpixmap.isNull.return_value = True  # pylint: disable=protected-access

        with patch("examples.factories.qt.qt_thumbnail_factory.isinstance", return_value=True):
            result = self.factory.validate(mock_qpixmap)
            assert result is False

    def test_validate_invalid_type(self):
        """Test invalid type validation."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        with patch("examples.factories.qt.qt_thumbnail_factory.isinstance", return_value=False):
            assert self.factory.validate("string") is False
            assert self.factory.validate(None) is False
            assert self.factory.validate(123) is False

    def test_reset_always_true(self):
        """Test reset always returns True."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        assert self.factory.reset(self.mock_qpixmap_class()) is True
        assert self.factory.reset(None) is True

    def test_estimate_size_success(self):
        """Test successful size estimation."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        mock_qpixmap = self.mock_qpixmap_class()
        mock_qpixmap._width = 200  # pylint: disable=protected-access
        mock_qpixmap._height = 150  # pylint: disable=protected-access
        mock_qpixmap._depth = 24  # pylint: disable=protected-access

        result = self.factory.estimate_size(mock_qpixmap)
        assert result == 200 * 150 * 3  # 24 // 8 = 3

    def test_estimate_size_different_depths(self):
        """Test estimation with different depths."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        # 32 bits
        mock_qpixmap = self.mock_qpixmap_class()
        mock_qpixmap._width = 100  # pylint: disable=protected-access
        mock_qpixmap._height = 100  # pylint: disable=protected-access
        mock_qpixmap._depth = 32  # pylint: disable=protected-access

        result = self.factory.estimate_size(mock_qpixmap)
        assert result == 100 * 100 * 4  # 32 // 8 = 4

    def test_estimate_size_exception(self):
        """Test estimation with exception."""
        if not self.qt_available:
            pytest.skip("PyQt6 not available")

        class _BadQPixmap:
            """Helper class for testing problematic QPixmap sizing."""

            # pylint: disable=too-few-public-methods
            def width(self):
                """Raises an AttributeError."""
                raise AttributeError("Width error")

        result = self.factory.estimate_size(_BadQPixmap())
        assert result == 1024
