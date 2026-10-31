"""Read-only, vehicle-scoped search hits for sourced repair procedures.

The search result identifies *where* a literal match occurs so the Windows
editor can jump to the exact step. Only user-owned/licensed records already
stored in AtelierData are queried; no external data or technical values.
"""
from __future__ import annotations

from repair_procedures import list_procedures

DEFAULT_LIMIT = 250
PROCEDURE_FIELDS = (
    ("title", "Titlu procedură"),
    ("system", "Sistem"),
    ("summary", "Rezumat"),
    ("precautions", "Avertisment general"),
    ("source", "Proveniență procedură"),
)
STEP_FIELDS = (
    ("instruction", "Instrucțiune pas"),
    ("safety_note", "Avertisment pas"),
    ("article_title", "Titlu document"),
    ("article_category", "Categorie document"),
    ("article_content", "Conținut document"),
    ("article_source", "Proveniență document"),
)


def _excerpt(value, needle, radius=85):
    """Bound text displayed in the results table, preserving the match."""
    value = str(value or "").replace("\r", " ").replace("\n", " ")
    index = value.casefold().find(needle.casefold())
    if index < 0:
        return value[:radius * 2]
    start = max(0, index - radius)
    end = min(len(value), index + len(needle) + radius)
    return ("…" if start else "") + value[start:end] + ("…" if end < len(value) else "")


def filter_hit_indices(hits, field=None):
    """Stable indices for one matching field, or all fields when unfiltered.

    The original result list is never mutated: the GUI can use these indices
    as stable row identifiers while navigating a filtered subset.
    """
    if field is None:
        return list(range(len(hits)))
    return [index for index, hit in enumerate(hits) if hit["field"] == field]


def next_hit_index(hit_count, current_index=None, direction=1):
    """Return the next/previous displayed search row, wrapping at the ends.

    This pure helper is shared by the Windows results dialog and unit tests.
    A missing selection starts at the first (next) or last (previous) row.
    """
    if (isinstance(hit_count, bool) or not isinstance(hit_count, int)
            or not 0 <= hit_count <= 1000):
        raise ValueError("Invalid search result count")
    if isinstance(direction, bool) or direction not in (-1, 1):
        raise ValueError("Invalid search navigation direction")
    if current_index is not None and (
            isinstance(current_index, bool) or not isinstance(current_index, int)
            or not 0 <= current_index < hit_count):
        raise ValueError("Invalid selected search result")
    if not hit_count:
        return None
    if current_index is None:
        return 0 if direction == 1 else hit_count - 1
    return (current_index + direction) % hit_count


def list_procedure_hits(store, vehicle_id, search, limit=DEFAULT_LIMIT, offset=0, field=None):
    """Find literal matches with exact step IDs and verified vehicle provenance.

    Each matching procedure metadata field yields a hit without a step ID.
    Each matching step field yields its own hit, so warnings and document
    provenance are not hidden by an earlier match in the same step. Document
    fields are included only when article.vehicle_id == procedure.vehicle_id.
    Offset-based pages preserve deterministic order and the same vehicle scope.
    No schema changes, commits, downloads or writes are performed.
    """
    # Search hits are exposed by the Windows dialog for one selected vehicle.
    # Never allow an omitted/invalid vehicle to silently query every vehicle.
    if isinstance(vehicle_id, bool) or not isinstance(vehicle_id, int) or vehicle_id <= 0:
        raise ValueError("Invalid vehicle id")
    if not isinstance(search, str) or not search.strip():
        raise ValueError("Introduce un termen de căutare")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("Limită invalidă")
    if isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 1000000:
        raise ValueError("Invalid search offset")
    valid_fields = {label for _, label in (*PROCEDURE_FIELDS, *STEP_FIELDS)}
    if field is not None and (not isinstance(field, str) or field not in valid_fields):
        raise ValueError('Invalid search field')
    # Reuse the canonical literal SQL search and its vehicle/length validation.
    procedures = list_procedures(store, vehicle_id, search)
    needle = search.casefold()
    results = []
    seen = 0

    def collect(hit):
        nonlocal seen
        if field is not None and hit['field'] != field:
            return False
        if seen >= offset:
            results.append(hit)
        seen += 1
        return len(results) >= limit

    procedure_field_labels = {label for _, label in PROCEDURE_FIELDS}
    for procedure in procedures:
        pid = procedure["id"]
        for key, label in PROCEDURE_FIELDS:
            if field is not None and field != label:
                continue
            value = procedure[key] or ""
            if needle in value.casefold():
                if collect({
                    "procedure_id": pid, "procedure_title": procedure["title"],
                    "step_id": None, "step_number": None,
                    "field": label, "excerpt": _excerpt(value, search),
                    "source": procedure["source"],
                }):
                    return results
        if len(results) >= limit:
            return results[:limit]
        # A metadata-only filter must not fetch step/document bodies.
        if field in procedure_field_labels:
            continue
        rows = store.db.execute("""
            SELECT s.id, s.step_number, s.instruction, s.safety_note,
                   a.title AS article_title, a.category AS article_category,
                   a.content AS article_content, a.source AS article_source
              FROM procedure_steps s
              LEFT JOIN articles a
                ON a.id=s.article_id AND a.vehicle_id=?
             WHERE s.procedure_id=?
             ORDER BY s.step_number,s.id
        """, (procedure["vehicle_id"], pid))
        for step in rows:
            for key, label in STEP_FIELDS:
                if field is not None and field != label:
                    continue
                value = step[key] or ""
                if needle in value.casefold():
                    doc_field = key.startswith("article_")
                    if collect({
                        "procedure_id": pid, "procedure_title": procedure["title"],
                        "step_id": step["id"], "step_number": step["step_number"],
                        "field": label, "excerpt": _excerpt(value, search),
                        "source": step["article_source"] if doc_field else procedure["source"],
                    }):
                        return results
            if len(results) >= limit:
                return results[:limit]
    return results
