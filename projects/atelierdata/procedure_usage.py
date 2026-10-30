"""Read-only reverse references: which repair steps use a user-owned document.

Only local SQLite metadata is read; no proprietary database is accessed.
The requested article must belong to the requested vehicle. A stale or
cross-vehicle reference is never exposed in the result.
"""
from __future__ import annotations


def list_document_usage(store, vehicle_id, article_id):
    """Return procedures and steps that reference one article for this vehicle.

    Each result includes source attribution, the general precaution and the
    step-level warning, allowing the GUI to navigate without losing context.
    The function does not create tables, indexes, or modify the database.
    """
    if (isinstance(vehicle_id, bool) or not isinstance(vehicle_id, int)
            or vehicle_id <= 0 or isinstance(article_id, bool)
            or not isinstance(article_id, int) or article_id <= 0):
        raise ValueError("Identificator vehicul/document invalid")
    article = store.db.execute(
        "SELECT id,vehicle_id FROM articles WHERE id=?", (article_id,)
    ).fetchone()
    if article is None or article["vehicle_id"] != vehicle_id:
        raise ValueError("Documentul nu aparține vehiculului selectat")
    return store.db.execute("""
        SELECT p.id AS procedure_id,p.vehicle_id,p.system,p.title,
               p.source,p.precautions,
               s.id AS step_id,s.step_number,s.instruction,s.safety_note,
               s.article_id
          FROM procedure_steps AS s
          JOIN procedures AS p ON p.id=s.procedure_id
         WHERE s.article_id=? AND p.vehicle_id=?
         ORDER BY p.system COLLATE NOCASE,p.title COLLATE NOCASE,
                  p.id,s.step_number,s.id
    """, (article_id,vehicle_id)).fetchall()
