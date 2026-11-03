"""Verify a search hit against live, same-vehicle SQLite records before navigation.

Results are snapshots; the matched field, document identity and ownership may
change before a user clicks. Only user-provided/licensed local records are read.
"""
from __future__ import annotations

from procedure_search_hits import PROCEDURE_FIELDS, STEP_FIELDS


def validate_live_hit(store, vehicle_id, hit, search):
    """Return True only if the original field still matches within its scope.

    A stale result raises ValueError. No schema or stored data is modified.
    SQL identifiers come exclusively from the fixed field allowlist.
    """
    if type(vehicle_id) is not int or vehicle_id <= 0:
        raise ValueError("Invalid vehicle ID")
    if not isinstance(hit, dict):
        raise ValueError("Invalid search hit")
    if not isinstance(search, str) or not search.strip() or len(search) > 200 or "\0" in search:
        raise ValueError("Invalid search term")
    pid = hit.get("procedure_id")
    if type(pid) is not int or pid <= 0:
        raise ValueError("Invalid procedure ID")
    label = hit.get("field")
    if not isinstance(label, str):
        raise ValueError("Invalid search field")
    procedure_columns = dict((display, column) for column, display in PROCEDURE_FIELDS)
    step_columns = dict((display, column) for column, display in STEP_FIELDS)
    if label in procedure_columns:
        if hit.get("step_id") is not None or hit.get("article_id") is not None:
            raise ValueError("Invalid procedure search hit")
        column = procedure_columns[label]
        row = store.db.execute(
            f"SELECT p.{column} AS value FROM procedures p "
            "WHERE p.id=? AND p.vehicle_id=?", (pid, vehicle_id)
        ).fetchone()
    elif label in step_columns:
        sid = hit.get("step_id")
        if type(sid) is not int or sid <= 0:
            raise ValueError("Invalid step ID")
        column = step_columns[label]
        if column.startswith("article_"):
            article_id = hit.get("article_id")
            if type(article_id) is not int or article_id <= 0:
                raise ValueError("Invalid document search hit")
            article_column = column[len("article_"):]
            row = store.db.execute(
                f"SELECT a.{article_column} AS value FROM procedure_steps s "
                "JOIN procedures p ON p.id=s.procedure_id "
                "JOIN articles a ON a.id=s.article_id AND a.vehicle_id=p.vehicle_id "
                "WHERE s.id=? AND p.id=? AND p.vehicle_id=? AND a.id=?",
                (sid, pid, vehicle_id, article_id)
            ).fetchone()
        else:
            if hit.get("article_id") is not None:
                raise ValueError("Invalid step search hit")
            row = store.db.execute(
                f"SELECT s.{column} AS value FROM procedure_steps s "
                "JOIN procedures p ON p.id=s.procedure_id "
                "WHERE s.id=? AND p.id=? AND p.vehicle_id=?",
                (sid, pid, vehicle_id)
            ).fetchone()
    else:
        raise ValueError("Unknown search field")
    if row is None or not isinstance(row["value"], str) or search.casefold() not in row["value"].casefold():
        raise ValueError("Search result changed or no longer belongs to the selected vehicle")
    return True
