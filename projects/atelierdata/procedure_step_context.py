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
    if isinstance(row["procedure_source"], str) and row["procedure_source"].strip():
        lines.append("SURSĂ PROCEDURĂ: " + row["procedure_source"].strip())
    if isinstance(row["precautions"], str) and row["precautions"].strip():
        lines.append("AVERTISMENT GENERAL: " + row["precautions"].strip())
    if isinstance(row["safety_note"], str) and row["safety_note"].strip():
        lines.append("ATENȚIE LA ACEST PAS: " + row["safety_note"].strip())
    if row["article_id"] is not None:
        if row["reference_title"] is None:
            lines.append("AVERTISMENT REFERINȚĂ: Document indisponibil sau asociat "
                         "altui vehicul; verifică auditul.")
        elif not isinstance(row["reference_title"], str) or not row["reference_title"].strip():
            # Imported/corrupt metadata must not crash the GUI or expose a
            # misleading document reference. Treat it as unavailable.
            lines.append("AVERTISMENT REFERINȚĂ: Titlul documentului este invalid; verifică auditul.")
        else:
            lines.append("DOCUMENT ASOCIAT: " + row["reference_title"].strip())
            if isinstance(row["reference_source"], str) and row["reference_source"].strip():
                lines.append("SURSĂ DOCUMENT: " + row["reference_source"].strip())
    return "\n".join(lines)
