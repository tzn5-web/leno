"""Read-only, vehicle-scoped context for a selected repair step.

Technical content is user-authored/licensed; this module never supplies repair values.
"""
from __future__ import annotations


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
    lines = [f"PAS {row['step_number']}: {row['instruction']}"]
    if row["procedure_source"]:
        lines.append("SURSĂ PROCEDURĂ: " + row["procedure_source"])
    if row["precautions"]:
        lines.append("AVERTISMENT GENERAL: " + row["precautions"])
    if row["safety_note"]:
        lines.append("ATENȚIE LA ACEST PAS: " + row["safety_note"])
    if row["article_id"] is not None:
        if row["reference_title"] is None:
            lines.append("AVERTISMENT REFERINȚĂ: Document indisponibil sau asociat "
                         "altui vehicul; verifică auditul.")
        else:
            lines.append("DOCUMENT ASOCIAT: " + row["reference_title"])
            if row["reference_source"]:
                lines.append("SURSĂ DOCUMENT: " + row["reference_source"])
    return "\n".join(lines)
