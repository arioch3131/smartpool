"""Tests for PILImageFactory."""

from unittest.mock import Mock, PropertyMock

import pytest  # pylint: disable=unused-import
from PIL import Image

from examples.factories import PILImageFactory
from smartpool.core.exceptions import FactoryCreationError, FactoryKeyGenerationError


class TestPILImageFactory:  # pylint: disable=attribute-defined-outside-init
    """Tests for PILImageFactory."""

    def test_create(self):
        """Test creating a PIL Image object."""
        factory = PILImageFactory()
        img = factory.create(width=50, height=60, mode="RGB")
        assert isinstance(img, Image.Image)
        assert img.size == (50, 60)
        assert img.mode == "RGB"
        with pytest.raises(FactoryCreationError):
            img = factory.create(width=None, height=None, mode=None)
        with pytest.raises(FactoryCreationError):
            img = factory.create(width="A", height="Z", mode=21)

    def test_validate(self):
        """Test the validation of a PIL Image."""
        factory = PILImageFactory()
        img = factory.create(width=10, height=10)
        assert factory.validate(img)

        # Test with _closed attribute
        mock_closed_img = Mock()
        mock_closed_img.width = 10
        mock_closed_img.height = 10
        mock_closed_img._closed = True  # pylint: disable=protected-access
        assert not factory.validate(mock_closed_img)

        # Test validate() exception (forcing exception in width access)
        mock_error_img = Mock()
        mock_error_img.width = PropertyMock(side_effect=Exception("Width access failed"))
        mock_error_img.height = 10  # Ensure height is valid
        assert not factory.validate(mock_error_img)

        # Test validate() exception (forcing exception in height access)
        mock_error_img_height = Mock()
        mock_error_img_height.width = 10
        mock_error_img_height.height = PropertyMock(side_effect=Exception("Height access failed"))
        assert not factory.validate(mock_error_img_height)

        # Test validate() exception (forcing exception in height access)
        mock_error_img_height = Mock()
        mock_error_img_height.width = 10
        mock_error_img_height.height = PropertyMock(side_effect=Exception("Height access failed"))
        assert not factory.validate(mock_error_img_height)

        invalid_img = Image.new("RGB", (0, 0))
        assert not factory.validate(invalid_img)

    def test_reset_rgb(self):
        """Test that an RGB image is correctly reset to black."""
        factory = PILImageFactory(enable_reset=True)
        img = factory.create(width=10, height=10, mode="RGB")
        img.paste((255, 0, 0), [0, 0, 10, 10])  # Fill with red
        assert img.getpixel((5, 5)) == (255, 0, 0)

        assert factory.reset(img)
        assert img.getpixel((5, 5)) == (0, 0, 0)

    def test_reset_rgba(self):
        """Test that an RGBA image is correctly reset to transparent black."""
        factory = PILImageFactory(enable_reset=True)
        img = factory.create(width=10, height=10, mode="RGBA")
        img.paste((255, 0, 0, 255), [0, 0, 10, 10])  # Fill with opaque red
        assert img.getpixel((5, 5)) == (255, 0, 0, 255)

        assert factory.reset(img)
        assert img.getpixel((5, 5)) == (0, 0, 0, 0)

    def test_reset_l_mode(self):
        """Test that an L mode image is correctly reset to black (0)."""
        factory = PILImageFactory(enable_reset=True)
        img = factory.create(width=10, height=10, mode="L")
        img.paste(255, [0, 0, 10, 10])  # Fill with white
        assert img.getpixel((5, 5)) == 255

        assert factory.reset(img)
        assert img.getpixel((5, 5)) == 0

    def test_reset_disabled(self):
        """Test that reset does nothing when disabled."""
        factory = PILImageFactory(enable_reset=False)
        img = factory.create(width=10, height=10, mode="RGB")
        img.paste((255, 0, 0), [0, 0, 10, 10])

        assert factory.reset(img)
        # Pixel should remain red because reset is a no-op
        assert img.getpixel((5, 5)) == (255, 0, 0)

    def test_get_key(self):
        """Test the key generation logic."""
        factory = PILImageFactory()
        key1 = factory.get_key(width=100, height=200, mode="RGB")
        assert key1 == "100x200_RGB"
        key2 = factory.get_key(width=800, height=600, mode="L")
        assert key2 == "800x600_L"
        key3 = factory.get_key(800, 600, mode="RGB")
        assert key3 == "800x600_RGB"
        with pytest.raises(FactoryKeyGenerationError):
            _ = factory.get_key(None, None)

    def test_destroy(self):
        """Test that the destroy method calls close() on the image."""
        factory = PILImageFactory()
        img = factory.create(width=10, height=10)
        # PIL images don't have a public `closed` attribute, so we just check for no exceptions
        try:
            factory.destroy(img)
        except Exception as e:  # pylint: disable=broad-exception-caught
            pytest.fail(f"factory.destroy() raised an exception: {e}")

    def test_estimate_size(self):
        """Test the size estimation for various image modes."""
        factory = PILImageFactory()
        w, h = 10, 10

        img_rgb = factory.create(w, h, "RGB")
        assert factory.estimate_size(img_rgb) == w * h * 3

        img_rgba = factory.create(w, h, "RGBA")
        assert factory.estimate_size(img_rgba) == w * h * 4

        img_l = factory.create(w, h, "L")
        assert factory.estimate_size(img_l) == w * h * 1

        img_f = factory.create(w, h, "F")  # 32-bit float
        assert factory.estimate_size(img_f) == w * h * 4

    def test_exception_branches(self):
        """Test the exception handling branches for 100% coverage."""
        factory = PILImageFactory()
        mock_image = Mock()

        # Test reset() exception
        mock_image.mode = "RGB"  # Set a mode to enter the try block
        mock_image.paste.side_effect = ValueError("Paste failed")
        assert not factory.reset(mock_image)

        # Test validate() exception
        mock_image.reset_mock()
        type(mock_image).width = PropertyMock(side_effect=AttributeError("Width failed"))
        assert not factory.validate(mock_image)

        # Test destroy() exception
        mock_image.reset_mock()
        mock_image.close.side_effect = OSError("Close failed")
        try:
            factory.destroy(mock_image)
        except Exception as e:  # pylint: disable=broad-exception-caught
            pytest.fail(f"destroy() should not raise exceptions, but raised {e}")

    def test_estimate_size_unknown_mode(self):
        """Test size estimation for an unknown image mode."""
        factory = PILImageFactory()
        mock_image = Mock()
        mock_image.mode = "UNKNOWN"
        mock_image.width = 10
        mock_image.height = 10
        # Should fall back to the default value of 4 bytes per pixel
        assert factory.estimate_size(mock_image) == 10 * 10 * 4
