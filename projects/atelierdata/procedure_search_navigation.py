"""Final read-only guard for search navigation after the Tkinter list redraw.

The first live-hit check occurs before refreshing the UI; this second check
closes the window in which SQLite data or the selected GUI row can change.
Only user-owned/licensed local records are read.
"""
from __future__ import annotations

from procedure_search_live import validate_live_hit


def require_live_navigation_target(store, vehicle_id, hit, search,
                                   selected_procedure_id, selected_step_id):
    """Accept a jump only when both the live match and GUI target agree."""
    validate_live_hit(store, vehicle_id, hit, search)
    expected_procedure = hit["procedure_id"]
    if (type(selected_procedure_id) is not int
            or selected_procedure_id != expected_procedure):
        raise ValueError("Selected procedure changed during navigation")
    expected_step = hit.get("step_id")
    if expected_step is not None and (
            type(selected_step_id) is not int
            or selected_step_id != expected_step):
        raise ValueError("Selected step changed during navigation")
    return True
