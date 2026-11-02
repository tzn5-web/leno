"""Read-only, vehicle-scoped warning-to-step navigation targets.

Only warnings explicitly recorded in the local licensed/user-owned SQLite
catalog are returned. No missing safety instructions are inferred.
"""
from __future__ import annotations


def warning_step_targets(store, vehicle_id, procedure_id):
    """Return (step_id, step_number, safety_note) tuples in current step order.

    The LEFT JOIN retains a valid procedure even if it has no step warnings.
    Procedure ownership and step membership are checked in one SQL statement.
    """
    for label, value in (("vehicle", vehicle_id), ("procedure", procedure_id)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"Invalid {label} ID")
    rows = store.db.execute(
        """SELECT s.id AS step_id, s.step_number, s.safety_note
           FROM procedures p
           LEFT JOIN procedure_steps s
             ON s.procedure_id=p.id
             AND TRIM(COALESCE(s.safety_note, '')) <> ''
           WHERE p.id=? AND p.vehicle_id=?
           ORDER BY s.step_number, s.id""",
        (procedure_id, vehicle_id),
    ).fetchall()
    if not rows:
        raise ValueError("Procedure does not belong to selected vehicle")
    return tuple(
        (row["step_id"], row["step_number"], row["safety_note"])
        for row in rows if row["step_id"] is not None
    )
