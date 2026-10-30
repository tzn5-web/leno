"""Read-only provenance and integrity audit for user-supplied repair procedures.

No OEM data is downloaded or inferred. Checks are scoped to the selected
procedure and its vehicle, including the managed files' SHA256 digests.
"""
from __future__ import annotations

from pathlib import Path

from atelierdata_extensions import list_documents, resolve_document
from repair_procedures import get_procedure, list_steps
from schematic_viewer import image_metadata

SCHEMATIC_CATEGORIES = frozenset(("Scheme electrice", "Siguranțe și relee"))
IMAGE_SUFFIXES = frozenset((".png", ".jpg", ".jpeg"))


def get_step_reference(store, step_id, vehicle_id, procedure_id):
    """Return the article only when both the step and article belong to this vehicle."""
    row = store.db.execute(
        "SELECT s.article_id,p.vehicle_id FROM procedure_steps s "
        "JOIN procedures p ON p.id=s.procedure_id "
        "WHERE s.id=? AND s.procedure_id=?", (step_id, procedure_id)
    ).fetchone()
    if row is None or row["vehicle_id"] != vehicle_id:
        raise ValueError("Pasul nu aparține procedurii/vehiculului selectat")
    if row["article_id"] is None:
        return None
    article = store.db.execute(
        "SELECT * FROM articles WHERE id=?", (row["article_id"],)
    ).fetchone()
    if article is None:
        raise ValueError("Referința nu mai există")
    if article["vehicle_id"] != vehicle_id:
        raise ValueError("Referința aparține altui vehicul")
    return article


def audit_procedure(store, procedure_id):
    """Return a deterministic, read-only report with per-step findings.

    A passing result means no errors; warnings may remain. A valid SHA256 only
    verifies storage integrity, not technical correctness or content licensing.
    """
    proc = get_procedure(store, procedure_id)
    if proc is None:
        raise ValueError("Procedura nu există")
    issues = []
    checked = 0
    def flag(severity, code, detail, step=None, attachment_id=None):
        issues.append({
            "severity": severity, "code": code, "detail": detail,
            "step_id": None if step is None else step["id"],
            "step_number": None if step is None else step["step_number"],
            "attachment_id": attachment_id,
        })

    if not proc["source"].strip():
        flag("ERROR", "PROCEDURE_SOURCE_MISSING", "Procedura nu are sursă documentată")
    steps = list_steps(store, procedure_id)
    if not steps:
        flag("WARNING", "PROCEDURE_EMPTY", "Procedura nu conține pași")
    seen = set()
    for expected, step in enumerate(steps, 1):
        number = step["step_number"]
        if number != expected or number in seen:
            flag("ERROR", "STEP_ORDER_INVALID", "Numerotarea pașilor este discontinuă", step)
        seen.add(number)
        if not step["instruction"].strip():
            flag("ERROR", "STEP_INSTRUCTION_MISSING", "Instrucțiunea este goală", step)
        if step["article_id"] is None:
            continue
        article = store.db.execute(
            "SELECT id,vehicle_id,category,title,source FROM articles WHERE id=?",
            (step["article_id"],)
        ).fetchone()
        if article is None:
            flag("ERROR", "REFERENCE_MISSING", "Documentul asociat a dispărut", step)
            continue
        if article["vehicle_id"] != proc["vehicle_id"]:
            flag("ERROR", "REFERENCE_OTHER_VEHICLE",
                 "Documentul aparține altui vehicul; accesul este blocat", step)
            continue
        if not article["source"].strip():
            flag("WARNING", "REFERENCE_SOURCE_MISSING",
                 "Documentul asociat nu indică proveniența", step)
        docs = list_documents(store, article["id"])
        has_previewable_image = False
        for doc in docs:
            try:
                verified_path = resolve_document(store, doc["id"])
                checked += 1
                if Path(verified_path).suffix.lower() in IMAGE_SUFFIXES:
                    try:
                        image_metadata(verified_path)
                    except (ValueError, OSError) as exc:
                        flag("ERROR", "SCHEMATIC_IMAGE_INVALID",
                             "Imaginea nu poate fi previzualizată: " + str(exc),
                             step, doc["id"])
                    else:
                        has_previewable_image = True
            except (ValueError, OSError) as exc:
                flag("ERROR", "ATTACHMENT_INTEGRITY_FAILED",
                     "Fișier lipsă, cale invalidă sau SHA256 diferit: " + str(exc),
                     step, doc["id"])
        if article["category"] in SCHEMATIC_CATEGORIES and not has_previewable_image:
            flag("WARNING", "SCHEMATIC_IMAGE_UNAVAILABLE",
                 "Schema nu are o imagine PNG/JPEG verificată pentru previzualizare", step)

    errors = sum(i["severity"] == "ERROR" for i in issues)
    warnings = sum(i["severity"] == "WARNING" for i in issues)
    return {
        "procedure_id": proc["id"],
        "vehicle_id": proc["vehicle_id"],
        "source": proc["source"],
        "steps": len(steps),
        "verified_attachments": checked,
        "errors": errors,
        "warnings": warnings,
        "ok": errors == 0,
        "issues": issues,
    }
