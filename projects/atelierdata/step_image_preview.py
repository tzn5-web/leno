"""Verified, read-only image preview for a current repair-procedure step.

Only user-owned/licensed managed attachments are eligible. No OEM content is
inferred, no external viewer is launched, and SQLite is never modified.
"""
from __future__ import annotations

from document_image_preview import read_verified_image_preview
from procedure_audit import get_step_reference


def read_step_image_preview(store, step_id, vehicle_id, procedure_id, attachment_id):
    """Return a detached RGB PIL image after current step/vehicle/link checks.

    Re-check both step and attachment ownership after decoding: a popup may
    remain open while an article or attachment is reassigned in SQLite.
    """
    for label, value in (("step", step_id), ("vehicle", vehicle_id),
                         ("procedure", procedure_id), ("attachment", attachment_id)):
        if type(value) is not int or value <= 0:
            raise ValueError("Invalid " + label + " ID")
    article = get_step_reference(store, step_id, vehicle_id, procedure_id)
    if article is None:
        raise ValueError("Pasul nu mai are document asociat")
    linked = store.db.execute(
        "SELECT 1 FROM attachments WHERE id=? AND article_id=?",
        (attachment_id, article["id"])).fetchone()
    if linked is None:
        raise ValueError("Atașamentul nu mai aparține documentului asociat")
    image = read_verified_image_preview(
        store, attachment_id, vehicle_id=vehicle_id, article_id=article["id"])
    current = get_step_reference(store, step_id, vehicle_id, procedure_id)
    if current is None or current["id"] != article["id"]:
        raise ValueError("Legătura pasului s-a modificat în timpul previzualizării")
    linked = store.db.execute(
        "SELECT 1 FROM attachments WHERE id=? AND article_id=?",
        (attachment_id, article["id"])).fetchone()
    if linked is None:
        raise ValueError("Atașamentul a fost reasociat în timpul previzualizării")
    return image
