"""Tests for the QPixmapFactory."""

# pylint: disable=redefined-outer-name, unused-argument, too-few-public-methods

import sys
from unittest.mock import Mock

import pytest
from PyQt6.QtGui import QColor, QImage, QPixmap  # pylint: disable=no-name-in-module
from PyQt6.QtWidgets import QApplication  # pylint: disable=no-name-in-module

from examples.factories import QPixmapFactory
from smartpool.core.exceptions import FactoryCreationError


@pytest.fixture(scope="session")
def qapp_fixture():
    """Initialize QApplication for tests."""
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app
    # No explicit app.quit() here, as pytest handles session teardown


@pytest.fixture
def qpixmap_factory_fixture(qapp_fixture):
    """Provide a QPixmapFactory instance for each test."""
    return QPixmapFactory()


class TestQPixmapFactoryInitialization:
    """Tests for QPixmapFactory initialization."""

    def test_init_default_values(self, qpixmap_factory_fixture):
        """Test initialization with default values."""
        factory = QPixmapFactory()
        assert factory.default_format == QImage.Format.Format_ARGB32
        assert factory.reset_color == QColor(0, 0, 0, 0)

    def test_init_custom_values(self, qpixmap_factory_fixture):
        """Test initialization with custom values."""
        custom_color = QColor(255, 0, 0, 128)
        factory = QPixmapFactory(
            default_format=QImage.Format.Format_RGB32, reset_color=custom_color
        )
        assert factory.default_format == QImage.Format.Format_RGB32
        assert factory.reset_color == custom_color


class TestQPixmapFactoryCreation:
    """Tests for QPixmapFactory create method."""

    def test_create_valid_dimensions(self, qpixmap_factory_fixture):
        """Test creating a QPixmap with valid dimensions."""
        pixmap = qpixmap_factory_fixture.create(100, 50)
        assert isinstance(pixmap, QPixmap)
        assert not pixmap.isNull()
        assert pixmap.width() == 100
        assert pixmap.height() == 50
        # Check if filled with reset color (black, alpha may vary by format)
        image = pixmap.toImage()
        pixel_color = image.pixelColor(0, 0)
        assert pixel_color.red() == 0
        assert pixel_color.green() == 0
        assert pixel_color.blue() == 0
        # Note: alpha value may vary depending on the pixmap format

    def test_create_with_specific_format(self, qpixmap_factory_fixture):
        """Test creating a QPixmap with a specified format."""
        pixmap = qpixmap_factory_fixture.create(10, 10, pixel_format=QImage.Format.Format_RGB888)
        assert isinstance(pixmap, QPixmap)
        assert not pixmap.isNull()
        assert pixmap.width() == 10
        assert pixmap.height() == 10
        # RGB888 format doesn't support alpha, so we only check RGB values
        image = pixmap.toImage()
        pixel_color = image.pixelColor(0, 0)
        assert pixel_color.red() == 0
        assert pixel_color.green() == 0
        assert pixel_color.blue() == 0
        # Alpha may not be 0 for RGB888 format, so we don't check it

    def test_create_invalid_dimensions(self, qpixmap_factory_fixture):
        """Test creating a QPixmap with invalid dimensions."""
        with pytest.raises(FactoryCreationError):
            qpixmap_factory_fixture.create(0, 50)
        with pytest.raises(FactoryCreationError):
            qpixmap_factory_fixture.create(100, 0)
        with pytest.raises(FactoryCreationError):
            qpixmap_factory_fixture.create(-10, 50)
        with pytest.raises(FactoryCreationError):
            qpixmap_factory_fixture.create(100, -50)


class TestQPixmapFactoryReset:
    """Tests for QPixmapFactory reset method."""

    def test_reset_valid_pixmap(self, qpixmap_factory_fixture):
        """Test resetting a valid QPixmap."""
        pixmap = qpixmap_factory_fixture.create(10, 10)
        # Fill with a different color to ensure reset works
        pixmap.fill(QColor(255, 0, 0))
        assert qpixmap_factory_fixture.reset(pixmap)
        image = pixmap.toImage()
        pixel_color = image.pixelColor(0, 0)
        # After reset, should be back to reset color (black, alpha may vary by format)
        assert pixel_color.red() == 0
        assert pixel_color.green() == 0
        assert pixel_color.blue() == 0
        # Note: alpha value may vary depending on the pixmap format

    def test_reset_null_pixmap(self, qpixmap_factory_fixture):
        """Test resetting a null QPixmap."""
        pixmap = QPixmap()
        assert not qpixmap_factory_fixture.reset(pixmap)

    def test_reset_exception_handling(self, qpixmap_factory_fixture):
        """Test reset method's exception handling."""
        mock_pixmap = Mock(spec=QPixmap)
        mock_pixmap.isNull.return_value = False
        mock_pixmap.fill.side_effect = RuntimeError("Fill failed")
        assert not qpixmap_factory_fixture.reset(mock_pixmap)


class TestQPixmapFactoryValidation:
    """Tests for QPixmapFactory validate method."""

    def test_validate_valid_pixmap(self, qpixmap_factory_fixture):
        """Test validating a valid QPixmap."""
        pixmap = qpixmap_factory_fixture.create(10, 10)
        assert qpixmap_factory_fixture.validate(pixmap)

    def test_validate_null_pixmap(self, qpixmap_factory_fixture):
        """Test validating a null QPixmap."""
        pixmap = QPixmap()
        assert not qpixmap_factory_fixture.validate(pixmap)

    def test_validate_invalid_dimensions(self, qpixmap_factory_fixture):
        """Test validating a QPixmap with invalid dimensions."""
        pixmap = QPixmap(0, 0)  # Create a pixmap with invalid dimensions
        assert not qpixmap_factory_fixture.validate(pixmap)

    def test_validate_non_qpixmap_object(self, qpixmap_factory_fixture):
        """Test validating a non-QPixmap object."""
        assert not qpixmap_factory_fixture.validate("not a pixmap")

    def test_validate_exception_handling(self, qpixmap_factory_fixture):
        """Test validate method's exception handling."""
        mock_pixmap = Mock(spec=QPixmap)
        mock_pixmap.isNull.side_effect = RuntimeError("isNull failed")
        assert not qpixmap_factory_fixture.validate(mock_pixmap)


class TestQPixmapFactoryKeyGeneration:
    """Tests for QPixmapFactory key generation logic."""

    def test_get_key(self, qpixmap_factory_fixture):
        """Test key generation logic."""
        # Test with specific calculations (round to nearest 32):
        # width=100: (100 + 16) // 32 * 32 = 116 // 32 * 32 = 3 * 32 = 96
        # height=200: (200 + 16) // 32 * 32 = 216 // 32 * 32 = 6 * 32 = 192
        key1 = qpixmap_factory_fixture.get_key(100, 200, QImage.Format.Format_ARGB32)
        assert key1 == "qpixmap_96x192_Format_ARGB32"

        # width=10: (10 + 16) // 32 * 32 = 26 // 32 * 32 = 0 * 32 = 0
        # height=10: (10 + 16) // 32 * 32 = 26 // 32 * 32 = 0 * 32 = 0
        key2 = qpixmap_factory_fixture.get_key(10, 10, QImage.Format.Format_RGB888)
        assert key2 == "qpixmap_0x0_Format_RGB888"

        # width=32: (32 + 16) // 32 * 32 = 48 // 32 * 32 = 1 * 32 = 32
        # height=32: (32 + 16) // 32 * 32 = 48 // 32 * 32 = 1 * 32 = 32
        key3 = qpixmap_factory_fixture.get_key(32, 32)  # Using default format
        assert key3 == "qpixmap_32x32_Format_ARGB32"


class TestQPixmapFactoryDestruction:
    """Tests for QPixmapFactory destroy method."""

    def test_destroy(self, qpixmap_factory_fixture):
        """Test destroy method."""
        pixmap = qpixmap_factory_fixture.create(10, 10)
        # No direct way to assert detachment, but ensure no exceptions
        try:
            qpixmap_factory_fixture.destroy(pixmap)
        except (AttributeError, RuntimeError) as e:
            pytest.fail(f"destroy() raised an exception: {e}")

    def test_destroy_null_pixmap(self, qpixmap_factory_fixture):
        """Test destroying a null pixmap."""
        pixmap = QPixmap()
        try:
            qpixmap_factory_fixture.destroy(pixmap)
        except (AttributeError, RuntimeError) as e:
            pytest.fail(f"destroy() raised an exception for null pixmap: {e}")

    def test_destroy_exception_handling(self, qpixmap_factory_fixture):
        """Test destroy method's exception handling."""
        mock_pixmap = Mock(spec=QPixmap)
        mock_pixmap.isNull.return_value = False
        mock_pixmap.detach.side_effect = RuntimeError("Detach failed")
        try:
            qpixmap_factory_fixture.destroy(mock_pixmap)
        except (AttributeError, RuntimeError) as e:
            pytest.fail(f"destroy() should handle exceptions, but raised {e}")


class TestQPixmapFactorySizeEstimation:
    """Tests for QPixmapFactory size estimation."""

    def test_estimate_size(self, qpixmap_factory_fixture):
        """Test size estimation.

        Note: Qt may optimize pixel formats internally for performance reasons.
        For example, a Grayscale8 format might be stored as 32-bit internally.
        Therefore, we use flexible ranges rather than exact values.
        """
        pixmap_rgb32 = qpixmap_factory_fixture.create(
            10, 10, pixel_format=QImage.Format.Format_RGB32
        )
        size_rgb32 = qpixmap_factory_fixture.estimate_size(pixmap_rgb32)
        # For 10x10 pixels, Qt may optimize formats, expect reasonable range
        assert size_rgb32 >= 100  # At least 1 byte per pixel
        assert size_rgb32 <= 1000  # At most ~10 bytes per pixel with overhead

        pixmap_rgb888 = qpixmap_factory_fixture.create(
            10, 10, pixel_format=QImage.Format.Format_RGB888
        )
        size_rgb888 = qpixmap_factory_fixture.estimate_size(pixmap_rgb888)
        # For RGB888, expect reasonable range
        assert size_rgb888 >= 100
        assert size_rgb888 <= 1000

        pixmap_grayscale = qpixmap_factory_fixture.create(
            10, 10, pixel_format=QImage.Format.Format_Grayscale8
        )
        size_grayscale = qpixmap_factory_fixture.estimate_size(pixmap_grayscale)
        # Qt may optimize grayscale to 32-bit internally, so expect reasonable range
        assert size_grayscale >= 100
        assert size_grayscale <= 1000

    def test_estimate_size_null_pixmap(self, qpixmap_factory_fixture):
        """Test size estimation for a null pixmap."""
        pixmap = QPixmap()
        assert qpixmap_factory_fixture.estimate_size(pixmap) == 0

    def test_estimate_size_exception_handling(self, qpixmap_factory_fixture):
        """Test estimate_size method's exception handling."""
        mock_pixmap = Mock(spec=QPixmap)
        mock_pixmap.isNull.return_value = False
        mock_pixmap.width.side_effect = AttributeError("Width access failed")
        # Should fall back to sys.getsizeof, which will return a non-zero value for a mock object
        assert qpixmap_factory_fixture.estimate_size(mock_pixmap) > 0


class TestQPixmapFactoryInfo:
    """Tests for QPixmapFactory info method."""

    def test_get_format_info(self, qpixmap_factory_fixture):
        """Test get_format_info method."""
        info = qpixmap_factory_fixture.get_format_info()
        assert isinstance(info, dict)
        assert "default_format" in info
        assert "reset_color" in info
        assert "supported_formats" in info
        assert info["default_format"] == "Format_ARGB32"
        assert info["reset_color"] == {"red": 0, "green": 0, "blue": 0, "alpha": 0}
        assert isinstance(info["supported_formats"], list)
