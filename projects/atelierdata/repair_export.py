"""Offline, printable exports of user-authored AtelierData repair procedures.

Exports are inert text only. Referenced attachments are not copied or embedded;
the verified ZIP backup is the mechanism for retaining original documents.
"""
from __future__ import annotations
import html
import json
import os
import tempfile
from pathlib import Path
from repair_procedures import get_procedure,list_procedures,list_steps

def _write_atomic(store,destination,content):
    target=Path(destination)
    if target.resolve()==store.path.resolve():
        raise ValueError("Refuz suprascrierea bazei SQLite")
    target.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix=".atelierdata-export-",dir=str(target.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return target

def _record(store,procedure):
    vehicle=store.db.execute(
        "SELECT make,model,engine,years,fuel,variant FROM vehicles WHERE id=?",
        (procedure["vehicle_id"],)).fetchone()
    return {
        "vehicle":dict(vehicle),
        "system":procedure["system"],
        "title":procedure["title"],
        "summary":procedure["summary"],
        "precautions":procedure["precautions"],
        "source":procedure["source"],
        "steps":[{
            "step_number":step["step_number"],
            "instruction":step["instruction"],
            "safety_note":step["safety_note"],
            "reference_article_id":step["article_id"],
            "reference_title":step["reference_title"]
        } for step in list_steps(store,procedure["id"])]
    }

def export_procedures_json(store,destination,vehicle_id=None):
    rows=[_record(store,p) for p in list_procedures(store,vehicle_id)]
    payload={
        "schema":"atelierdata-repair-procedures-v1",
        "content":"User-authored or authorized entries only",
        "attachment_bytes_included":False,
        "procedures":rows
    }
    _write_atomic(store,destination,json.dumps(payload,indent=2,ensure_ascii=False))
    return len(rows)

def procedure_html(store,procedure_id):
    p=get_procedure(store,procedure_id)
    if p is None:raise ValueError("Procedură inexistentă")
    record=_record(store,p)
    esc=lambda value:html.escape(str(value),quote=True)
    vehicle=record["vehicle"]
    identity=" / ".join(filter(None,(vehicle["make"],vehicle["model"],
                                   vehicle["engine"],vehicle["years"])))
    parts=[
      "<!doctype html><html lang='ro'><head><meta charset='utf-8'>",
      "<meta http-equiv='Content-Security-Policy' "
      "content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">",
      "<meta name='viewport' content='width=device-width,initial-scale=1'>",
      "<title>"+esc(record["title"])+"</title>",
      "<style>body{font:16px/1.5 system-ui,Arial,sans-serif;max-width:900px;"
      "margin:2rem auto;padding:0 1.5rem;color:#162438}"
      "h1{font-size:2rem}h2{margin-top:1.8rem}.meta{color:#46556a}"
      ".warning{border-left:5px solid #b3312a;background:#fff1ee;padding:1rem}"
      ".step{break-inside:avoid;margin:1.3rem 0;padding:1rem;border:1px solid #ccd4dc}"
      ".reference{font-size:.9rem;color:#46556a}"
      "@media print{body{margin:0;max-width:none}.step{page-break-inside:avoid}}</style>",
      "</head><body><header><h1>"+esc(record["title"])+"</h1>",
      "<p class='meta'><strong>Vehicul:</strong> "+esc(identity)+"<br>",
      "<strong>Sistem:</strong> "+esc(record["system"])+"<br>",
      "<strong>Sursă:</strong> "+esc(record["source"])+"</p></header>"
    ]
    if record["summary"]:
        parts.append("<h2>Descriere</h2><p>"+esc(record["summary"])+"</p>")
    if record["precautions"]:
        parts.append("<section class='warning'><strong>Avertismente generale</strong><p>"
                     +esc(record["precautions"])+"</p></section>")
    parts.append("<h2>Pași de lucru</h2>")
    if not record["steps"]:
        parts.append("<p>Nu există pași introduși pentru această procedură.</p>")
    for step in record["steps"]:
        parts.append("<section class='step'><h3>Pasul "+str(step["step_number"])+"</h3>"
                     "<p>"+esc(step["instruction"])+"</p>")
        if step["safety_note"]:
            parts.append("<p class='warning'><strong>Atenție:</strong> "
                         +esc(step["safety_note"])+"</p>")
        if step["reference_title"]:
            parts.append("<p class='reference'>Document asociat: "
                         +esc(step["reference_title"])+"</p>")
        parts.append("</section>")
    parts.append("<footer><hr><p class='meta'>Acest document reproduce numai informațiile "
                 "introduse sau importate autorizat. Fișierele atașate nu sunt incluse. "
                 "Verifică sursa și aplicabilitatea înainte de orice intervenție.</p>"
                 "</footer></body></html>")
    return "\n".join(parts)

def export_procedure_html(store,procedure_id,destination):
    if Path(destination).suffix.lower() not in (".html",".htm"):
        raise ValueError("Exportul imprimabil trebuie să fie HTML")
    return _write_atomic(store,destination,procedure_html(store,procedure_id))
