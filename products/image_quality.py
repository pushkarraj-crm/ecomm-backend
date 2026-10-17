"""Conservative technical checks; content/branding decisions remain human-reviewed."""

from PIL import Image, ImageOps, ImageFilter, ImageStat, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

MIN_SIDE = 400
MAX_PIXELS = 25_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def check_catalog_image(upload):
    try:
        upload.seek(0)
        with Image.open(upload) as source:
            if (
                source.format not in ALLOWED_FORMATS
                or getattr(source, "n_frames", 1) > 1
            ):
                raise ValidationError("Use a static JPG, PNG or WebP product image.")
            width, height = source.size
            if min(width, height) < MIN_SIDE:
                raise ValidationError(
                    f"Image resolution is too low. Use at least {MIN_SIDE} × {MIN_SIDE} pixels."
                )
            if width * height > MAX_PIXELS:
                raise ValidationError(
                    "Image dimensions are too large. Use an image below 25 megapixels."
                )
            if max(width, height) / min(width, height) > 3:
                raise ValidationError(
                    "The image is too wide or tall. Use a less extreme aspect ratio."
                )
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((512, 512))
            gray = ImageOps.grayscale(image)
            if ImageStat.Stat(gray).stddev[0] < 3:
                raise ValidationError(
                    "The image is blank or too unclear. Upload a clear product photograph."
                )
            edges = gray.filter(ImageFilter.FIND_EDGES)
            if min(edges.size) > 8:
                edges = edges.crop((3, 3, edges.width - 3, edges.height - 3))
            stats = ImageStat.Stat(edges)
            if stats.var[0] < 8 and stats.mean[0] < 0.7:
                raise ValidationError(
                    "The image appears strongly blurred. Upload a sharper photograph."
                )
            return {
                "width": width,
                "height": height,
                "sharpness": round(stats.var[0], 2),
                "status": "pending_review",
            }
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError(
            "The image could not be read safely. Choose a valid product photo."
        )
    finally:
        upload.seek(0)
