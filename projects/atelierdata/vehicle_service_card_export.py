"""Offline printable HTML service sheet, with exact sources and no invented values."""
import html
import os
import tempfile
from pathlib import Path
from vehicle_service_card import card,SECTIONS

def export_vehicle_card_html(store,vehicle_id,destination):
    result=card(store,vehicle_id)
    p=Path(destination)
    if p.suffix.lower() not in (".htm",".html"):
        raise ValueError("Fișa trebuie exportată HTML")
    if p.resolve()==store.path.resolve():
        raise ValueError("Nu suprascrie baza SQLite")
    v=result["vehicle"]
    quote=lambda value:html.escape(str(value or ""),quote=True)
    lines=[
        "<!doctype html><html lang='ro'><head><meta charset='utf-8'>",
        "<title>AtelierData — fișă tehnică</title>",
        "<style>@page{size:A4;margin:12mm}body{font:13px Arial,sans-serif;color:#182331;margin:25px;}",
        "h1{font-size:22px}h2{background:#e7eff7;padding:9px;border-left:4px solid #2a6487}",
        "table{border-collapse:collapse;width:100%;margin:10px 0 18px}",
        "td,th{border:1px solid #c5ced8;padding:7px;vertical-align:top;text-align:left}",
        "th{background:#f0f4f7}td.missing{color:#8a4b35;font-style:italic}",
        ".note{color:#6c4b28;font-weight:bold}.small{font-size:11px;color:#506476}",
        "</style></head><body><h1>FIȘĂ TEHNICĂ VEHICUL</h1>",
        "<p><strong>"+quote(v["make"])+" "+quote(v["model"])+"</strong> | "
        +quote(v["years"])+" | Motor (declarat): "+quote(v["engine"])+
        " | Combustibil: "+quote(v["fuel"])+" | Variantă: "+quote(v["variant"])+"</p>",
        "<p class='note'>Valorile neconfirmate nu trebuie utilizate pentru întreținere."
        " Verifică manualul, anul, motorizarea și condițiile fiecărei valori.</p>",
    ]
    for section in SECTIONS:
        lines.append("<h2>"+quote(section)+"</h2><table><thead><tr>"
                     "<th style='width:31%'>Parametru</th><th>Valoare</th><th>Condiții</th><th>Sursă</th>"
                     "</tr></thead><tbody>")
        for i,field in enumerate(result["fields"]):
            if field[0]!=section:continue
            records=result["values"][i] or [None]
            for entry in records:
                if entry is None:
                    lines.append("<tr><td>"+quote(field[1])+"</td>"
                       "<td class='missing'>NECONFIRMAT</td><td>—</td><td>—</td></tr>")
                else:
                    lines.append("<tr><td>"+quote(field[1])+"</td><td><strong>"
                        +quote(entry["value"])+" "+quote(entry["unit"])+"</strong></td><td>"
                        +quote(entry["conditions"])+"</td><td>"+quote(entry["source"])+"</td></tr>")
        lines.append("</tbody></table>")
    lines.append("<p class='small'>Fișă generată local din AtelierData. "
                 "Sursele sunt declarate, nu verificate automat de producător. "
                 "Nu conține specificații OEM preinstalate.</p></body></html>")
    p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".atelierdata-card-",dir=str(p.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            f.write("\n".join(lines));f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return {"path":str(p),"fields":result["total_count"],
            "sourced":result["sourced_count"]}
