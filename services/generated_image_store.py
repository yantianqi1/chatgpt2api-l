from __future__ import annotations

from pathlib import Path
import uuid
from urllib.parse import quote

from services.config import config

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURES = (b"\xff\xd8\xff",)
WEBP_SIGNATURE = b"WEBP"
GIF_SIGNATURE = b"GIF8"
CONTENT_TYPE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _extension_from_signature(image_bytes: bytes) -> str:
    if image_bytes.startswith(PNG_SIGNATURE):
        return ".png"
    if any(image_bytes.startswith(signature) for signature in JPEG_SIGNATURES):
        return ".jpg"
    if len(image_bytes) >= 12 and image_bytes[8:12] == WEBP_SIGNATURE:
        return ".webp"
    if image_bytes.startswith(GIF_SIGNATURE):
        return ".gif"
    return ".png"


def _resolve_extension(content_type: str | None, image_bytes: bytes) -> str:
    normalized = str(content_type or "").split(";")[0].strip().lower()
    if normalized in CONTENT_TYPE_EXTENSIONS:
        return CONTENT_TYPE_EXTENSIONS[normalized]
    return _extension_from_signature(image_bytes)


def build_generated_image_url(file_name: str) -> str:
    return f"{config.public_base_url}/generated-images/{quote(file_name)}"


def save_generated_image(image_bytes: bytes, content_type: str | None = None) -> str:
    extension = _resolve_extension(content_type, image_bytes)
    file_name = f"{uuid.uuid4().hex}{extension}"
    output_path = Path(config.generated_images_dir) / file_name
    output_path.write_bytes(image_bytes)
    return build_generated_image_url(file_name)
