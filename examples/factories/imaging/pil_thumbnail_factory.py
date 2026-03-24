"""Factory for generating PIL Image thumbnails with caching support."""

import os
from typing import Any, cast

from PIL import Image

from smartpool import ObjectFactory


class PilThumbnailFactory(ObjectFactory[Image.Image]):
    """Factory to generate PIL Image thumbnails."""

    def __init__(
        self, format_handlers: Any, pil_generator: Any, placeholder_generator: Any, logger: Any
    ) -> None:
        self.format_handlers = format_handlers
        self.pil_generator = pil_generator
        self.placeholder_generator = placeholder_generator
        self.logger = logger

    def get_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate cache key for thumbnail."""
        image_path, size, quality_factor = args
        return f"{image_path}_{size[0]}x{size[1]}_{quality_factor}"

    def create(self, *args: Any, **kwargs: Any) -> Image.Image:
        """Create thumbnail image with fallback to placeholder on failure."""
        image_path, size, quality_factor = args
        try:  # pylint: disable=duplicate-code
            handler = self.format_handlers.get(
                os.path.splitext(image_path)[1].lower(), self.pil_generator.generate
            )
            thumbnail = handler(image_path, size, quality_factor)
            if thumbnail is None:
                self.logger.warning(
                    f"PIL Thumbnail generation failed for {image_path}, using placeholder."
                )
                thumbnail = self.placeholder_generator.generate(image_path, size)
            return cast(Image.Image, thumbnail)
        except (IOError, ValueError) as e:
            self.logger.error(f"Exception in PilThumbnailFactory create for {image_path}: {e}")
            return cast(Image.Image, self.placeholder_generator.generate(image_path, size))

    def validate(self, obj: Image.Image) -> bool:
        """Validate that object is a PIL Image."""
        return isinstance(obj, Image.Image)

    def reset(self, obj: Image.Image) -> bool:
        """Reset object state (thumbnails are immutable)."""
        return True  # Thumbnails are immutable

    def estimate_size(self, obj: Image.Image) -> int:
        """Estimate memory size of PIL Image object."""
        try:
            return obj.width * obj.height * len(obj.getbands())
        except (AttributeError, TypeError):
            return 1024  # Fallback size
