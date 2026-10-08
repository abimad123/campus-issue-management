from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError

MAX_ISSUE_IMAGE_BYTES = 5 * 1024 * 1024
MAX_ISSUE_IMAGE_PIXELS = 20_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_issue_image(upload):
    if upload.size > MAX_ISSUE_IMAGE_BYTES:
        raise ValidationError("Images must be 5 MB or smaller.")
    try:
        upload.seek(0)
        image = Image.open(upload)
        if image.format not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError("Upload a JPEG, PNG, or WebP image.")
        if image.width * image.height > MAX_ISSUE_IMAGE_PIXELS:
            raise ValidationError("Images must be 20 megapixels or smaller.")
        image.verify()
        upload.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("The uploaded file is not a valid image.") from None


def issue_attachment_path(instance, filename):
    return f"issue-attachments/{instance.issue_id}/{filename}"
