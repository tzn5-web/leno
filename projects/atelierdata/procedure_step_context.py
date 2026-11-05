"""Read-only, vehicle-scoped context for a selected repair step.

Technical content is user-authored/licensed; this module never supplies repair values.
"""
from __future__ import annotations

import unicodedata


def _has_unsafe_display_controls(value):
    """Block Unicode format controls that can visually reorder GUI evidence."""
    return any(unicodedata.category(char) in ("Cc", "Cf") for char in value)


def _safe_display_text(value):
    """Reject control characters that could forge extra GUI context lines."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or _has_unsafe_display_controls(value):
        return None
    return value


def step_context_text(store, vehicle_id, procedure_id, step_id):
    """Render a current SQLite step with warnings and provenance, without foreign data."""
    for label, value in (("vehicle", vehicle_id), ("procedure", procedure_id),
                         ("step", step_id)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"Invalid {label} ID")
    row = store.db.execute(
        """SELECT s.step_number, s.instruction, s.safety_note, s.article_id,
                  p.precautions, p.source AS procedure_source,
                  a.title AS reference_title, a.source AS reference_source
           FROM procedures p
           JOIN procedure_steps s ON s.procedure_id=p.id
           LEFT JOIN articles a
             ON a.id=s.article_id AND a.vehicle_id=p.vehicle_id
           WHERE p.id=? AND p.vehicle_id=? AND s.id=?""",
        (procedure_id, vehicle_id, step_id)).fetchone()
    if row is None:
        raise ValueError("Step no longer belongs to selected vehicle and procedure")
    if not isinstance(row["instruction"], str) or not row["instruction"].strip():
        raise ValueError("Step instruction is missing or empty")
    if type(row["step_number"]) is not int or row["step_number"] <= 0:
        raise ValueError("Step number is invalid")
    if _has_unsafe_display_controls(row["instruction"]):
        raise ValueError("Step instruction contains a forbidden control character")
    lines = [f"PAS {row['step_number']}: {row['instruction'].strip()}"]
    for column, label in (
        ("procedure_source", "SURSĂ PROCEDURĂ"),
        ("precautions", "AVERTISMENT GENERAL"),
        ("safety_note", "ATENȚIE LA ACEST PAS"),
    ):
        value = _safe_display_text(row[column])
        if value is not None:
            lines.append(f"{label}: {value}")
    if row["article_id"] is not None:
        if row["reference_title"] is None:
            lines.append("AVERTISMENT REFERINȚĂ: Document indisponibil sau asociat "
                         "altui vehicul; verifică auditul.")
        elif _safe_display_text(row["reference_title"]) is None:
            # Imported/corrupt metadata must not crash the GUI or expose a
            # misleading document reference. Treat it as unavailable.
            lines.append("AVERTISMENT REFERINȚĂ: Titlul documentului este invalid; verifică auditul.")
        else:
            lines.append("DOCUMENT ASOCIAT: " + _safe_display_text(row["reference_title"]))
            reference_source = _safe_display_text(row["reference_source"])
            if reference_source is not None:
                lines.append("SURSĂ DOCUMENT: " + reference_source)
    return "\n".join(lines)
