"""Resolve a repair step's currently linked schematic within one SQLite snapshot.

Only user-authored/licensed local article metadata is consulted; no OEM data.
"""
from __future__ import annotations

from schematic_viewer import SCHEME_CATEGORIES


def linked_step_schematic_id(store, vehicle_id, procedure_id, step_id):
    """Return a same-vehicle schematic ID or reject a stale/invalid link.

    Joining the procedure, step and schematic in one SELECT avoids mixing
    unrelated reads when a link has been changed or removed.
    """
    for label, value in (("vehicle", vehicle_id), ("procedure", procedure_id),
                         ("step", step_id)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"Invalid {label} ID")
    row = store.db.execute(
        """SELECT a.id AS schematic_id
           FROM procedures p
           JOIN procedure_steps s ON s.procedure_id=p.id
           LEFT JOIN articles a ON a.id=s.article_id
                AND a.vehicle_id=p.vehicle_id
                AND a.category IN (?,?)
           WHERE p.id=? AND p.vehicle_id=? AND s.id=?""",
        (*SCHEME_CATEGORIES, procedure_id, vehicle_id, step_id),
    ).fetchone()
    if row is None:
        raise ValueError("Step no longer belongs to the selected vehicle and procedure")
    if row["schematic_id"] is None:
        raise ValueError("Step has no valid same-vehicle schematic link")
    return row["schematic_id"]
