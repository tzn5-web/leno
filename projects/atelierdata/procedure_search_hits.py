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


def list_procedure_hits(store, vehicle_id, search, limit=DEFAULT_LIMIT):
    """Find literal matches with exact step IDs and verified vehicle provenance.

    Each matching procedure metadata field yields a hit without a step ID.
    Each matching step field yields its own hit, so warnings and document
    provenance are not hidden by an earlier match in the same step. Document
    fields are included only when article.vehicle_id == procedure.vehicle_id.
    No schema changes, commits, downloads or writes are performed.
    """
    if not isinstance(search, str) or not search.strip():
        raise ValueError("Introduce un termen de căutare")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("Limită invalidă")
    # Reuse the canonical literal SQL search and its vehicle/length validation.
    procedures = list_procedures(store, vehicle_id, search)
    needle = search.casefold()
    results = []
    for procedure in procedures:
        pid = procedure["id"]
        for key, label in PROCEDURE_FIELDS:
            value = procedure[key] or ""
            if needle in value.casefold():
                results.append({
                    "procedure_id": pid, "procedure_title": procedure["title"],
                    "step_id": None, "step_number": None,
                    "field": label, "excerpt": _excerpt(value, search),
                    "source": procedure["source"],
                })
                if len(results) >= limit:
                    return results
        if len(results) >= limit:
            return results[:limit]
        rows = store.db.execute("""
            SELECT s.id, s.step_number, s.instruction, s.safety_note,
                   a.title AS article_title, a.category AS article_category,
                   a.content AS article_content, a.source AS article_source
              FROM procedure_steps s
              LEFT JOIN articles a
                ON a.id=s.article_id AND a.vehicle_id=?
             WHERE s.procedure_id=?
             ORDER BY s.step_number,s.id
        """, (procedure["vehicle_id"], pid)).fetchall()
        for step in rows:
            for key, label in STEP_FIELDS:
                value = step[key] or ""
                if needle in value.casefold():
                    doc_field = key.startswith("article_")
                    results.append({
                        "procedure_id": pid, "procedure_title": procedure["title"],
                        "step_id": step["id"], "step_number": step["step_number"],
                        "field": label, "excerpt": _excerpt(value, search),
                        "source": step["article_source"] if doc_field else procedure["source"],
                    })
                    if len(results) >= limit:
                        return results
            if len(results) >= limit:
                return results[:limit]
    return results
