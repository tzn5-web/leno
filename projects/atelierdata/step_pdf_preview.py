"""Read-only, vehicle-scoped PDF page preview for a repair-procedure step.

All PDF bytes are rendered by the existing verified library reader. The
step-to-article-to-attachment relationship is checked both before and after
rendering, so a stale procedure popup cannot disclose a reassigned document.
"""
from __future__ import annotations

from document_pdf_preview import read_verified_pdf_page
from document_library import verified_library_file
from procedure_audit import get_step_reference


def read_step_pdf_page(store, step_id, vehicle_id, procedure_id,
                       attachment_id, page_number=1):
    """Return (detached RGB image, page count) for a currently linked PDF.

    The PDF reader enforces SHA256, declared rights, PDF format and rendering
    limits. This wrapper additionally enforces the current step association,
    including after PDFium returns, without modifying SQLite.
    """
    for label, value in (("step", step_id), ("vehicle", vehicle_id),
                         ("procedure", procedure_id), ("attachment", attachment_id)):
        if type(value) is not int or value <= 0:
            raise ValueError("Invalid " + label + " ID")
    if type(page_number) is not int or page_number < 1:
        raise ValueError("Pagina PDF trebuie să fie un întreg pozitiv")

    article = get_step_reference(store, step_id, vehicle_id, procedure_id)
    if article is None:
        raise ValueError("Pasul nu mai are document asociat")
    linked = store.db.execute(
        "SELECT 1 FROM attachments WHERE id=? AND article_id=?",
        (attachment_id, article["id"])).fetchone()
    if linked is None:
        raise ValueError("Atașamentul nu mai aparține documentului asociat")

    image, page_count = read_verified_pdf_page(
        store, attachment_id, vehicle_id=vehicle_id,
        article_id=article["id"], page_number=page_number)

    current = get_step_reference(store, step_id, vehicle_id, procedure_id)
    if current is None or current["id"] != article["id"]:
        raise ValueError("Legătura pasului s-a modificat în timpul previzualizării")
    linked = store.db.execute(
        "SELECT 1 FROM attachments WHERE id=? AND article_id=?",
        (attachment_id, article["id"])).fetchone()
    if linked is None:
        raise ValueError("Atașamentul a fost reasociat în timpul previzualizării")
    # Recheck the current rights declaration and managed digest after rendering.
    # The image itself was decoded from the verified bytes, not from this path.
    verified_library_file(
        store, attachment_id, vehicle_id=vehicle_id,
        article_id=article["id"], require_declared_rights=True)
    return image, page_count
