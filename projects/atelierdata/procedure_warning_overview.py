"""Read-only warning overview for user-owned/licensed repair procedures.

This is an index of recorded warnings, not a safety certification.
"""
from __future__ import annotations


def warning_overview_text(store, vehicle_id, procedure_id):
    """Summarize current general and step warnings for exactly one vehicle.

    One SQLite SELECT keeps procedure ownership and ordered step notes in
    a single statement snapshot. No technical specifications are generated.
    """
    for label, value in (("vehicle", vehicle_id), ("procedure", procedure_id)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"Invalid {label} ID")
    rows = store.db.execute(
        """SELECT p.system, p.title, p.precautions, p.source,
                  s.step_number, s.safety_note
           FROM procedures p
           LEFT JOIN procedure_steps s ON s.procedure_id = p.id
           WHERE p.id = ? AND p.vehicle_id = ?
           ORDER BY s.step_number, s.id""",
        (procedure_id, vehicle_id),
    ).fetchall()
    if not rows:
        raise ValueError("Procedure does not belong to selected vehicle")
    first = rows[0]
    lines = [f"PROCEDURĂ: {first['system']} — {first['title']}",
             f"SURSĂ PROCEDURĂ: {first['source']}"]
    count = 0
    if first["precautions"]:
        lines.extend(("", "AVERTISMENT GENERAL:", first["precautions"]))
        count += 1
    for row in rows:
        if row["step_number"] is not None and row["safety_note"]:
            lines.extend(("", f"ATENȚIE — PAS {row['step_number']}:", row["safety_note"]))
            count += 1
    lines.extend(("", f"TOTAL AVERTISMENTE ÎNREGISTRATE: {count}"))
    if count == 0:
        lines.append("Nu sunt avertismente înregistrate. Aceasta nu confirmă că procedura este lipsită de riscuri.")
    return "\n".join(lines)
