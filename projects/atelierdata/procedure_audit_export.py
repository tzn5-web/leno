"""Export a reproducible, read-only audit snapshot for a single workshop procedure.

The JSON contains only locally entered metadata and integrity findings. No OEM
files, image bytes, licensed documentation or hidden technical values are copied.
"""
from __future__ import annotations

import json
from pathlib import Path

from procedure_audit import audit_procedure
from repair_export import _write_atomic


def export_procedure_audit_json(store, procedure_id, destination, vehicle_id=None):
    """Re-audit current SQLite state and atomically write a JSON report.

    A vehicle scope is required by the GUI and supported for all callers.
    Refuses overwriting SQLite or any file in managed attachment storage.
    """
    report = audit_procedure(store, procedure_id)
    if vehicle_id is not None and report["vehicle_id"] != vehicle_id:
        raise ValueError("Procedura aparține altui vehicul")

    target = Path(destination)
    if target.suffix.lower() != ".json":
        raise ValueError("Raportul de audit trebuie să aibă extensia .json")
    resolved = target.resolve()
    if resolved == store.path.resolve():
        raise ValueError("Refuz suprascrierea bazei SQLite")
    managed = (store.path.parent / "documents").resolve()
    if resolved == managed or managed in resolved.parents:
        raise ValueError("Refuz exportul în depozitul de atașamente")

    vehicle = store.db.execute(
        "SELECT make,model,engine,years,fuel,variant FROM vehicles WHERE id=?",
        (report["vehicle_id"],)
    ).fetchone()
    if vehicle is None:
        raise ValueError("Vehiculul procedurii nu mai există")

    payload = {
        "schema": "atelierdata-procedure-audit-v1",
        "purpose": "Audit of user-owned or authorized workshop documentation",
        "limitations": (
            "SHA256 confirms stored file integrity, not technical accuracy, "
            "completeness, applicability or permission to use documentation."
        ),
        "attachment_bytes_included": False,
        "vehicle": dict(vehicle),
        "audit": report,
    }
    _write_atomic(store, target, json.dumps(
        payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return payload
