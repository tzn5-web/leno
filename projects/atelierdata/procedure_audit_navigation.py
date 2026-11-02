"""Read-only, vehicle-scoped validation for navigation from an audit finding.

An audit window holds a historical report. Never treat its old step IDs or
finding descriptions as authorization to navigate after SQLite changes.
"""
from __future__ import annotations

from procedure_audit import audit_procedure


def require_live_audit_step(store, vehicle_id, procedure_id, issue):
    """Return the step ID only if the exact finding still exists for this vehicle."""
    for label, value in (("vehicle", vehicle_id), ("procedure", procedure_id)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"Invalid {label} ID")
    if not isinstance(issue, dict) or type(issue.get("step_id")) is not int:
        raise ValueError("Audit finding does not identify a step")
    if issue["step_id"] <= 0:
        raise ValueError("Invalid audit step ID")
    report = audit_procedure(store, procedure_id)
    if report["vehicle_id"] != vehicle_id:
        raise ValueError("Procedure no longer belongs to selected vehicle")
    if issue not in report["issues"]:
        raise ValueError("Audit finding is no longer current; refresh the audit")
    return issue["step_id"]
