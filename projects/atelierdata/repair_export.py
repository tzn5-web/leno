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
    resolved=target.resolve()
    if resolved==store.path.resolve():
        raise ValueError("Refuz suprascrierea bazei SQLite")
    # Exports must never replace managed attachments, even through symlinks.
    managed=(store.path.parent/"documents").resolve()
    if resolved==managed or managed in resolved.parents:
        raise ValueError("Refuz exportul în depozitul de atașamente")
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
    steps=[]
    for step in list_steps(store,procedure["id"]):
        # list_steps hides foreign/missing document metadata. Preserve the
        # warning in exports, without leaking the foreign article identifier.
        invalid=(step["article_id"] is not None and step["reference_title"] is None)
        status=("invalid_or_unavailable" if invalid else
                "linked" if step["article_id"] is not None else "none")
        steps.append({
            "step_number":step["step_number"],
            "instruction":step["instruction"],
            "safety_note":step["safety_note"],
            "reference_article_id":None if invalid else step["article_id"],
            "reference_title":None if invalid else step["reference_title"],
            "reference_source":None if invalid else step["reference_source"],
            "reference_status":status
        })
    return {
        "vehicle":dict(vehicle),
        "system":procedure["system"],
        "title":procedure["title"],
        "summary":procedure["summary"],
        "precautions":procedure["precautions"],
        "source":procedure["source"],
        "steps":steps
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
      ".warning{border-left:5px solid #b3312a;background:#fff1ee;padding:1rem;white-space:pre-wrap;overflow-wrap:anywhere}"
      ".step{break-inside:avoid;margin:1.3rem 0;padding:1rem;border:1px solid #ccd4dc}"
      ".safety-index{border:2px solid #b3312a;padding:1rem;margin:1.5rem 0;break-inside:avoid}"
      ".reference{font-size:.9rem;color:#46556a}" " .instruction{white-space:pre-wrap;overflow-wrap:anywhere}"
      ".completion{display:block;margin-top:.8rem;padding:.4rem .6rem;background:#eef4fa}"
      ".completion input{width:1.1rem;height:1.1rem;vertical-align:middle}"
      "@media print{nav{display:none}body{margin:0;max-width:none}.step{page-break-inside:avoid}}</style>",
      "</head><body><header><h1>"+esc(record["title"])+"</h1>",
      "<p class='meta'><strong>Vehicul:</strong> "+esc(identity)+"<br>",
      "<strong>Sistem:</strong> "+esc(record["system"])+"<br>",
      "<strong>Sursă:</strong> "+esc(record["source"])+"</p></header>"
    ]
    if record["summary"]:
        parts.append("<h2>Descriere</h2><p>"+esc(record["summary"])+"</p>")
    if record["precautions"]:
        parts.append("<section class='warning' id='avertismente-generale'>"
                     "<strong>Avertismente generale</strong><p>"
                     +esc(record["precautions"])+"</p></section>")
    # A printable, offline safety index makes warnings and broken references
    # discoverable before starting work. Link only to local step anchors.
    flagged = []
    for position, step in enumerate(record["steps"], 1):
        labels = []
        if step["safety_note"]:
            labels.append("Avertisment de siguranță")
        if step["reference_status"] == "invalid_or_unavailable":
            labels.append("Referință indisponibilă")
        if labels:
            flagged.append((position, step["step_number"], labels))
    if flagged or record["precautions"]:
        parts.append("<aside class='safety-index' aria-label='Avertismente și referințe'>"
                     "<h2>Verificări înainte de lucru</h2><ul>")
        if record["precautions"]:
            parts.append("<li><a href='#avertismente-generale'>"
                         "Avertismente generale</a></li>")
        for position, number, labels in flagged:
            parts.append("<li><a href='#pas-"+str(position)+"'>Pasul "
                         +esc(number)+"</a>: "+esc(" / ".join(labels))+"</li>")
        parts.append("</ul></aside>")
    parts.append("<h2>Pași de lucru</h2>")
    if record["steps"]:
        parts.append("<p class='meta'>Bifele marchează doar pașii parcurși în această "
                     "pagină. Nu se salvează și nu confirmă siguranța lucrării.</p>")
    if not record["steps"]:
        parts.append("<p>Nu există pași introduși pentru această procedură.</p>")
    if record["steps"]:
        # Fragment-only navigation works offline and never loads attachments.
        parts.append("<nav aria-label='Cuprinsul pașilor'><h2>Cuprins</h2><ol>")
        for position, step in enumerate(record["steps"], 1):
            flags = (" — Atenție" if step["safety_note"] else "")
            if step["reference_status"] == "invalid_or_unavailable":
                flags += " — Referință indisponibilă"
            elif step["reference_status"] == "linked":
                flags += " — Document asociat"
            parts.append("<li><a href='#pas-"+str(position)+"'>Pasul "
                         +esc(step["step_number"])+"</a>"+flags+"</li>")
        parts.append("</ol></nav>")
    for position, step in enumerate(record["steps"], 1):
        parts.append("<section class='step' id='pas-"+str(position)
                     +"'><h3>Pasul "+esc(step["step_number"])+"</h3>"
                     "<p class='instruction'>"+esc(step["instruction"])+"</p>")
        if step["safety_note"]:
            parts.append("<p class='warning'><strong>Atenție:</strong> "
                         +esc(step["safety_note"])+"</p>")
        if step["reference_status"]=="invalid_or_unavailable":
            parts.append("<p class='warning'><strong>AVERTISMENT REFERINȚĂ:</strong> "
                         "Document indisponibil sau asociat altui vehicul; "
                         "verifică auditul.</p>")
        if step["reference_title"]:
            parts.append("<p class='reference'>Document asociat: "
                         +esc(step["reference_title"])
                         +("<br>Sursă document: "+esc(step["reference_source"])
                           if step["reference_source"] else "")+"</p>")
        parts.append("<label class='completion'><input type='checkbox' id='parcurs-"
                     +str(position)+"'> <span>Pasul "+esc(step["step_number"])
                     +" parcurs</span></label>")
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
