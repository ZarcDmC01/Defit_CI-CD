from __future__ import annotations
from fastapi import UploadFile
from config import settings


class ValidationError(Exception):
    pass


async def validate_file(file: UploadFile) -> bytes:
    """Validate file extension and size; return raw bytes on success."""
    filename = file.filename or ""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in settings.allowed_extensions:
        raise ValidationError(
            f"Unsupported file type '{suffix}'. Allowed: {sorted(settings.allowed_extensions)}"
        )

    content = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValidationError(
            f"File exceeds {settings.max_file_size_mb} MB limit "
            f"({len(content) / 1024 / 1024:.2f} MB received)."
        )

    if len(content) == 0:
        raise ValidationError("Uploaded file is empty.")

    return content
