"""Bounded, offline PNG/JPEG preview of user-authorized library attachments.

Do not treat user-declared rights or file signatures as legal/malware certification.
The bytes displayed are SHA256-checked after the file is read, not only before it.
"""
from __future__ import annotations

import hashlib
from io import BytesIO

from document_library import verified_library_file

MAX_IMAGE_PREVIEW_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PREVIEW_PIXELS = 8_000_000


def read_verified_image_preview(store, attachment_id, vehicle_id=None, article_id=None):
    """Return an independent RGB PIL image; never write SQLite or launch a viewer."""
    path = verified_library_file(
        store, attachment_id, vehicle_id=vehicle_id, article_id=article_id,
        require_declared_rights=True)
    suffix = path.suffix.lower()
    if suffix not in (".png", ".jpg", ".jpeg"):
        raise ValueError("Previzualizarea imaginilor acceptă numai PNG/JPG/JPEG")
    with path.open("rb") as stream:
        payload = stream.read(MAX_IMAGE_PREVIEW_BYTES + 1)
    if len(payload) > MAX_IMAGE_PREVIEW_BYTES:
        raise ValueError("Imagine prea mare pentru previzualizare (maxim 16 MiB)")
    if hashlib.sha256(payload).hexdigest() != path.stem:
        raise ValueError("Atașament modificat sau corupt în timpul previzualizării")

    from PIL import Image, ImageOps, UnidentifiedImageError
    expected_format = "PNG" if suffix == ".png" else "JPEG"
    try:
        with Image.open(BytesIO(payload)) as source:
            if source.format != expected_format:
                raise ValueError("Formatul imaginii nu corespunde extensiei")
            if (source.width <= 0 or source.height <= 0 or
                    source.width * source.height > MAX_IMAGE_PREVIEW_PIXELS):
                raise ValueError("Imaginea depășește limita de 8 megapixeli")
            source.verify()
        with Image.open(BytesIO(payload)) as source:
            result = ImageOps.exif_transpose(source).convert("RGB")
            result.load()
            return result.copy()
    except (UnidentifiedImageError, OSError, SyntaxError,
            Image.DecompressionBombError) as exc:
        raise ValueError("Imagine invalidă pentru previzualizare") from exc
