"""Printable, offline HTML integrity report for user-owned repair procedures.

No remote assets, JavaScript, linked attachment bytes, or proprietary content.
A report is a snapshot of local checks, not an approval for vehicle repair.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from procedure_audit import audit_procedure
from repair_export import _write_atomic
from repair_procedures import get_procedure


def _safe_destination(store, destination):
    target = Path(destination)
    if target.suffix.lower() not in (".html", ".htm"):
        raise ValueError("Raportul de audit imprimabil trebuie să fie HTML")
    resolved = target.resolve()
    if resolved == store.path.resolve():
        raise ValueError("Refuz suprascrierea bazei SQLite")
    managed = (store.path.parent / "documents").resolve()
    if resolved == managed or managed in resolved.parents:
        raise ValueError("Refuz exportul în depozitul de atașamente")
    return target


def audit_html(store, procedure_id, vehicle_id=None):
    """Render fresh read-only findings. All database-origin strings are escaped."""
    report = audit_procedure(store, procedure_id)
    if vehicle_id is not None and report["vehicle_id"] != vehicle_id:
        raise ValueError("Procedura aparține altui vehicul")
    procedure = get_procedure(store, procedure_id)
    vehicle = store.db.execute(
        "SELECT make,model,engine,years,fuel,variant FROM vehicles WHERE id=?",
        (report["vehicle_id"],)
    ).fetchone()
    if procedure is None or vehicle is None:
        raise ValueError("Procedura sau vehiculul nu mai există")
    e = lambda value: escape(str(value), quote=True)
    identity = " / ".join(filter(None, (
        vehicle["make"], vehicle["model"], vehicle["engine"], vehicle["years"],
        vehicle["fuel"], vehicle["variant"])))
    parts = [
        "<!doctype html><html lang='ro'><head><meta charset='utf-8'>",
        "<meta http-equiv='Content-Security-Policy' "
        "content=\"default-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'\">",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>AtelierData — audit: " + e(procedure["title"]) + "</title>",
        "<style>body{font:15px/1.5 system-ui,Arial,sans-serif;max-width:1100px;"
        "margin:2rem auto;padding:0 1.5rem;color:#152439}"
        "h1{font-size:1.65rem}.muted{color:#4d5c70}"
        "table{border-collapse:collapse;width:100%;table-layout:fixed}"
        "th,td{border:1px solid #ccd4df;padding:.65rem;vertical-align:top;"
        "overflow-wrap:anywhere;text-align:left}"
        "th{background:#eaf0f8}.error{background:#ffefec}"
        ".warning{background:#fff8df}.ok{background:#e8f7ee}"
        ".summary{padding:.8rem;background:#eef3fa}"
        "@media print{body{margin:0;max-width:none}"
        "tr{break-inside:avoid}thead{display:table-header-group}}</style>",
        "</head><body>",
        "<h1>AtelierData — audit documentație</h1>",
        "<p><strong>Procedură:</strong> " + e(procedure["title"]) + "<br>",
        "<strong>Sistem:</strong> " + e(procedure["system"]) + "<br>",
        "<strong>Vehicul:</strong> " + e(identity) + "<br>",
        "<strong>Sursă:</strong> " + e(report["source"]) + "</p>",
        "<p class='summary'>Pași: " + str(report["steps"]) +
        " · Atașamente verificate SHA256: " + str(report["verified_attachments"]) +
        " · Erori: " + str(report["errors"]) +
        " · Avertismente: " + str(report["warnings"]) + "</p>",
        "<h2>Constatări</h2>",
    ]
    if report["issues"]:
        parts.append("<table><thead><tr><th>Nivel</th><th>Pas</th>"
                     "<th>Cod</th><th>Detalii</th></tr></thead><tbody>")
        for issue in report["issues"]:
            severity = issue["severity"]
            css = "error" if severity == "ERROR" else "warning"
            number = "—" if issue["step_number"] is None else str(issue["step_number"])
            parts.append(
                "<tr class='" + css + "'><td>" + e(severity) +
                "</td><td>" + e(number) + "</td><td>" + e(issue["code"]) +
                "</td><td>" + e(issue["detail"]) + "</td></tr>"
            )
        parts.append("</tbody></table>")
    else:
        parts.append("<p class='ok'>Nu au fost detectate probleme în verificările efectuate.</p>")
    parts.extend([
        "<hr><p class='muted'>Raport generat din datele locale la export. "
        "SHA256 confirmă numai integritatea fișierelor stocate, nu "
        "corectitudinea tehnică, compatibilitatea, completitudinea sau "
        "dreptul de utilizare. Verificați întotdeauna documentația autorizată. "
        "Raportul nu include fișierele atașate și nu execută instrucțiuni.</p>",
        "</body></html>",
    ])
    return "\n".join(parts)


def export_procedure_audit_html(store, procedure_id, destination, vehicle_id=None):
    """Validate the target, re-audit and atomically write inert printable HTML."""
    target = _safe_destination(store, destination)
    return _write_atomic(store, target, audit_html(store, procedure_id, vehicle_id))
