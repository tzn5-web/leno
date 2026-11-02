"""Read-only document navigation from a recorded warning in one SQLite snapshot.

The document and warning must belong to the same current vehicle/procedure/step.
This does not certify that user-provided technical instructions are correct.
"""
from __future__ import annotations


def warning_step_reference_id(store, vehicle_id, procedure_id, step_id):
    """Return (article_id, warning_text) only for a live, same-vehicle link."""
    for label, value in (("vehicle", vehicle_id), ("procedure", procedure_id),
                         ("step", step_id)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"Invalid {label} ID")
    row = store.db.execute(
        """SELECT s.safety_note, s.article_id, a.id AS authorized_article_id
           FROM procedures p
           JOIN procedure_steps s ON s.procedure_id=p.id
           LEFT JOIN articles a ON a.id=s.article_id
                                  AND a.vehicle_id=p.vehicle_id
           WHERE p.id=? AND p.vehicle_id=? AND s.id=?""",
        (procedure_id, vehicle_id, step_id),
    ).fetchone()
    if row is None:
        raise ValueError("Warning step no longer belongs to selected vehicle")
    if not isinstance(row["safety_note"], str) or not row["safety_note"].strip():
        raise ValueError("Selected step no longer has a recorded warning")
    if row["article_id"] is None:
        raise ValueError("Warning step has no linked document")
    if row["authorized_article_id"] is None:
        raise ValueError("Linked document is missing or belongs to another vehicle")
    return row["authorized_article_id"], row["safety_note"]
