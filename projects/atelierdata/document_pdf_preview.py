"""Bounded offline PDF preview of a user-authorized managed attachment.

Render from the exact bytes rehashed after reading, never from a mutable path.
A declared license or valid SHA256 does not establish legal or technical validity.
"""
from __future__ import annotations

import hashlib
from math import isfinite, sqrt

from document_library import verified_library_file

MAX_PDF_PREVIEW_BYTES = 32 * 1024 * 1024
MAX_PDF_PREVIEW_PAGES = 2000
MAX_PDF_PREVIEW_PIXELS = 8_000_000


def read_verified_pdf_page(store, attachment_id, vehicle_id=None,
                           article_id=None, page_number=1):
    """Return (independent RGB PIL image, page count), without SQLite writes."""
    if type(page_number) is not int or page_number < 1:
        raise ValueError("Pagina PDF trebuie să fie un întreg pozitiv")
    path = verified_library_file(
        store, attachment_id, vehicle_id=vehicle_id, article_id=article_id,
        require_declared_rights=True)
    if path.suffix.lower() != ".pdf":
        raise ValueError("Previzualizarea PDF acceptă numai fișiere PDF")
    with path.open("rb") as stream:
        payload = stream.read(MAX_PDF_PREVIEW_BYTES + 1)
    if len(payload) > MAX_PDF_PREVIEW_BYTES:
        raise ValueError("PDF prea mare pentru previzualizare (maxim 32 MiB)")
    if hashlib.sha256(payload).hexdigest() != path.stem:
        raise ValueError("Atașament modificat sau corupt în timpul previzualizării")
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("Lipsește pypdfium2 pentru previzualizarea PDF") from exc

    try:
        # Pass verified bytes, not the file path: PDFium cannot reopen a
        # different file between the digest check and page rendering.
        document = pdfium.PdfDocument(payload)
        try:
            pages = len(document)
            if not 1 <= pages <= MAX_PDF_PREVIEW_PAGES:
                raise ValueError("Număr de pagini PDF neacceptat")
            if page_number > pages:
                raise ValueError("Pagina PDF nu există")
            page = document[page_number - 1]
            try:
                width, height = page.get_size()
                if (not isfinite(width) or not isfinite(height)
                        or width <= 0 or height <= 0
                        or width > 20000 or height > 20000):
                    raise ValueError("Dimensiune pagină PDF invalidă")
                scale = min(1.7, sqrt(MAX_PDF_PREVIEW_PIXELS / (width * height)))
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil().convert("RGB")
                    image.load()
                    if image.width * image.height > MAX_PDF_PREVIEW_PIXELS:
                        raise ValueError("Pagina PDF depășește limita de 8 megapixeli")
                    return image.copy(), pages
                finally:
                    bitmap.close()
            finally:
                page.close()
        finally:
            document.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF invalid sau imposibil de redat") from exc
