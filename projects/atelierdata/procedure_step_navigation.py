"""Read-only navigation of sourced repair steps scoped to one vehicle."""
from __future__ import annotations


def adjacent_step_id(store, vehicle_id, procedure_id, current_step_id=None, direction=1):
    """Return adjacent live step ID or None at a boundary.

    No selection chooses first (+1) or last (-1). Deleted or foreign steps
    are rejected, not redirected. Vehicle and step membership share one SQLite\n    statement snapshot. Never modifies SQLite.
    """
    for label, value in (("vehicle", vehicle_id), ("procedure", procedure_id)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"Invalid {label} ID")
    if current_step_id is not None and (type(current_step_id) is not int or current_step_id <= 0):
        raise ValueError("Invalid step ID")
    if type(direction) is not int or direction not in (-1, 1):
        raise ValueError("Invalid navigation direction")
    # A LEFT JOIN returns one NULL step for an existing empty procedure.
    # No rows means the procedure is missing or belongs to another vehicle.
    # Ownership and ordering must be read in ONE SQLite statement snapshot:
    # separate SELECTs can observe different states after reassignment.
    rows = store.db.execute(
        "SELECT s.id FROM procedures p "
        "LEFT JOIN procedure_steps s ON s.procedure_id=p.id "
        "WHERE p.id=? AND p.vehicle_id=? "
        "ORDER BY s.step_number,s.id", (procedure_id, vehicle_id)
    ).fetchall()
    if not rows:
        raise ValueError("Procedure does not belong to selected vehicle")
    ids = [row[0] for row in rows if row[0] is not None]
    if current_step_id is None:
        return (ids[0] if direction == 1 else ids[-1]) if ids else None
    if current_step_id not in ids:
        raise ValueError("Step no longer belongs to selected procedure")
    target = ids.index(current_step_id) + direction
    return ids[target] if 0 <= target < len(ids) else None
