"""
Complete unit tests for PilThumbnailFactory - 100% coverage.
"""

# pylint: disable=W0201

from unittest.mock import Mock, patch

from PIL import Image

from examples.factories import PilThumbnailFactory

from .base_thumbnail_test import BaseThumbnailFactoryTest


class BasePilThumbnailTest(BaseThumbnailFactoryTest):  # pylint: disable=R0903, W0201
    """Base class for PilThumbnailFactory tests, providing common setup."""

    def setup_method(self):  # pylint: disable=W0201
        """Setup mocks for each test."""
        super().setup_method()
        self.factory = PilThumbnailFactory(
            format_handlers=self.format_handlers,
            pil_generator=self.pil_generator,
            placeholder_generator=self.placeholder_generator,
            logger=self.logger,
        )


class TestPilThumbnailFactoryInitialization(BasePilThumbnailTest):
    """Tests for PilThumbnailFactory initialization."""

    def test_init(self):
        """Test the constructor."""
        assert self.factory.format_handlers == self.format_handlers
        assert self.factory.pil_generator == self.pil_generator
        assert self.factory.placeholder_generator == self.placeholder_generator
        assert self.factory.logger == self.logger


class TestPilThumbnailFactoryKeyGeneration(BasePilThumbnailTest):
    """Tests for PilThumbnailFactory key generation."""

    def test_get_key_basic(self):
        """Test basic key generation."""
        image_path = "/path/to/image.jpg"
        size = (150, 150)
        quality_factor = 0.8

        result = self.factory.get_key(image_path, size, quality_factor)
        expected = "/path/to/image.jpg_150x150_0.8"

        assert result == expected

    def test_edge_cases(self):
        """Test edge cases for key generation."""
        # Size 0
        result = self.factory.get_key("/test.jpg", (0, 0), 1.0)
        assert result == "/test.jpg_0x0_1.0"

        # Negative quality factor
        result = self.factory.get_key("/test.jpg", (100, 100), -0.5)
        assert result == "/test.jpg_100x100_-0.5"

        # Empty path
        result = self.factory.get_key("", (100, 100), 0.8)
        assert result == "_100x100_0.8"


class TestPilThumbnailFactoryCreation(BasePilThumbnailTest):
    """Tests for PilThumbnailFactory object creation."""

    def test_create_success_with_handler(self):
        """Test successful creation with specific handler."""
        image_path = "/path/to/image.jpg"
        size = (150, 150)
        quality_factor = 0.8

        # Mock a PIL Image
        mock_image = Mock(spec=Image.Image)
        self.format_handlers[".jpg"].return_value = mock_image

        result = self.factory.create(image_path, size, quality_factor)

        assert result == mock_image
        self.format_handlers[".jpg"].assert_called_once_with(image_path, size, quality_factor)
        self.placeholder_generator.generate.assert_not_called()
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    def test_create_success_with_default_pil_generator(self):
        """Test creation with default pil_generator (unrecognized extension)."""
        image_path = "/path/to/image.bmp"  # Extension not in format_handlers
        size = (150, 150)
        quality_factor = 0.8

        mock_image = Mock(spec=Image.Image)
        self.pil_generator.generate.return_value = mock_image

        result = self.factory.create(image_path, size, quality_factor)

        assert result == mock_image
        self.pil_generator.generate.assert_called_once_with(image_path, size, quality_factor)
        self.placeholder_generator.generate.assert_not_called()

    def test_create_handler_returns_none_fallback_to_placeholder(self):
        """Test fallback to placeholder when handler returns None."""
        image_path = "/path/to/image.png"
        size = (150, 150)
        quality_factor = 0.8

        # Handler returns None
        self.format_handlers[".png"].return_value = None

        mock_placeholder = Mock(spec=Image.Image)
        self.placeholder_generator.generate.return_value = mock_placeholder

        result = self.factory.create(image_path, size, quality_factor)

        assert result == mock_placeholder
        self.format_handlers[".png"].assert_called_once_with(image_path, size, quality_factor)
        self.placeholder_generator.generate.assert_called_once_with(image_path, size)
        self.logger.warning.assert_called_once_with(
            f"PIL Thumbnail generation failed for {image_path}, using placeholder."
        )

    def test_create_exception_fallback_to_placeholder(self):
        """Test fallback to placeholder when an exception is raised."""
        image_path = "/path/to/image.gif"
        size = (150, 150)
        quality_factor = 0.8

        # Handler raises an exception
        test_exception = IOError("Test exception")
        self.format_handlers[".gif"].side_effect = test_exception

        mock_placeholder = Mock(spec=Image.Image)
        self.placeholder_generator.generate.return_value = mock_placeholder

        result = self.factory.create(image_path, size, quality_factor)

        assert result == mock_placeholder
        self.placeholder_generator.generate.assert_called_once_with(image_path, size)
        self.logger.error.assert_called_once_with(
            f"Exception in PilThumbnailFactory create for {image_path}: {test_exception}"
        )

    def test_create_case_insensitive_extensions(self):
        """Test that extensions are handled case-insensitively."""
        image_path = "/path/to/image.JPG"  # Uppercase extension
        size = (150, 150)
        quality_factor = 0.8

        mock_image = Mock(spec=Image.Image)
        self.format_handlers[".jpg"].return_value = mock_image

        result = self.factory.create(image_path, size, quality_factor)

        assert result == mock_image
        self.format_handlers[".jpg"].assert_called_once_with(image_path, size, quality_factor)

    def test_create_no_extension(self):
        """Test with file having no extension."""
        image_path = "/path/to/imagefile"  # No extension
        size = (150, 150)
        quality_factor = 0.8

        mock_image = Mock(spec=Image.Image)
        self.pil_generator.generate.return_value = mock_image

        result = self.factory.create(image_path, size, quality_factor)

        assert result == mock_image
        self.pil_generator.generate.assert_called_once_with(image_path, size, quality_factor)

    def test_create_pil_generator_returns_none(self):
        """Test when pil_generator returns None."""
        image_path = "/path/to/image.unknown"
        size = (150, 150)
        quality_factor = 0.8

        # pil_generator returns None
        self.pil_generator.generate.return_value = None

        mock_placeholder = Mock(spec=Image.Image)
        self.placeholder_generator.generate.return_value = mock_placeholder

        result = self.factory.create(image_path, size, quality_factor)

        assert result == mock_placeholder
        self.placeholder_generator.generate.assert_called_once_with(image_path, size)
        self.logger.warning.assert_called_once()

    def test_create_pil_generator_exception(self):
        """Test when pil_generator raises an exception."""
        image_path = "/path/to/image.unknown"
        size = (150, 150)
        quality_factor = 0.8

        # pil_generator raises an exception
        test_exception = IOError("PIL generator failed")
        self.pil_generator.generate.side_effect = test_exception

        mock_placeholder = Mock(spec=Image.Image)
        self.placeholder_generator.generate.return_value = mock_placeholder

        result = self.factory.create(image_path, size, quality_factor)

        assert result == mock_placeholder
        self.logger.error.assert_called_once_with(
            f"Exception in PilThumbnailFactory create for {image_path}: {test_exception}"
        )

    def test_multiple_extensions(self):
        """Test with files having multiple extensions."""
        image_path = "/path/to/image.backup.jpg"
        size = (100, 100)
        quality_factor = 0.8

        mock_image = Mock(spec=Image.Image)
        self.format_handlers[".jpg"].return_value = mock_image

        result = self.factory.create(image_path, size, quality_factor)

        assert result == mock_image
        self.format_handlers[".jpg"].assert_called_once_with(image_path, size, quality_factor)

    def test_format_handlers_modification(self):
        """Test that format_handlers can be modified."""
        # Add a new handler
        new_handler = Mock()
        self.factory.format_handlers[".webp"] = new_handler

        image_path = "/test/image.webp"
        size = (150, 150)
        quality_factor = 0.9

        mock_image = Mock(spec=Image.Image)
        new_handler.return_value = mock_image

        result = self.factory.create(image_path, size, quality_factor)

        assert result == mock_image
        new_handler.assert_called_once_with(image_path, size, quality_factor)

    def test_logger_integration(self):
        """Test full integration with the logger."""
        image_path = "/test/problematic.jpg"
        size = (100, 100)
        quality_factor = 0.8

        # First case: handler returns None
        self.format_handlers[".jpg"].return_value = None
        mock_placeholder = Mock(spec=Image.Image)
        self.placeholder_generator.generate.return_value = mock_placeholder

        self.factory.create(image_path, size, quality_factor)
        self.logger.warning.assert_called_once()

        # Reset the logger
        self.logger.reset_mock()

        # Second case: exception
        self.format_handlers[".jpg"].side_effect = IOError("File corrupted")

        self.factory.create(image_path, size, quality_factor)
        test_exception = IOError("File corrupted")
        self.logger.error.assert_called_once_with(
            f"Exception in PilThumbnailFactory create for {image_path}: {test_exception}"
        )

    def test_edge_cases(self):
        """Test edge cases for key generation."""
        # Size 0
        result = self.factory.get_key("/test.jpg", (0, 0), 1.0)
        assert result == "/test.jpg_0x0_1.0"

        # Negative quality factor
        result = self.factory.get_key("/test.jpg", (100, 100), -0.5)
        assert result == "/test.jpg_100x100_-0.5"

        # Empty path
        result = self.factory.get_key("", (100, 100), 0.8)
        assert result == "_100x100_0.8"


class TestPilThumbnailFactoryValidateReset(BasePilThumbnailTest):
    """Tests for PilThumbnailFactory key generation."""

    def test_validate(self):
        """Test Validate."""
        with patch(
            "examples.factories.imaging.pil_thumbnail_factory.isinstance",
            return_value=True,
        ):
            result = self.factory.validate([])
            assert result is True

    def test_reset(self):
        """Test Reset returns always True, as thumbnails are immutable."""
        result = self.factory.reset([])
        assert result is True


class TestPilThumbnailFactoryEstimateSize(BasePilThumbnailTest):
    """Tests for Estimate Size."""

    def test_estimate_size(self):
        """Tests a valid Image."""
        mock_image = Mock(spec=Image.Image)
        mock_image.width = 1024
        mock_image.height = 1024
        mock_image.getbands.return_value = "RGB"

        result = self.factory.estimate_size(mock_image)
        assert result == 1024 * 1024 * 3

    def test_estimate_size_type_error(self):
        """Tests an estimate size with a Image with bad type."""
        mock_image = Mock(spec=Image.Image)
        mock_image.width = None
        mock_image.height = 1024
        mock_image.getbands.return_value = 32

        result = self.factory.estimate_size(mock_image)
        assert result == 1024

    def test_estimate_size_image_none(self):
        """Tests an estimate size with None."""
        result = self.factory.estimate_size(None)
        assert result == 1024
