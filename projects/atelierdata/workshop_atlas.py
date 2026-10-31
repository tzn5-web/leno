"""Structured workshop facts and diagram markers for AtelierData.

All values are explicitly user supplied; NO manufacturer torque, location, fuse
or electrical data are synthesized. Source and exact vehicle association required.
SQLite add-only schema: compatible with existing AtelierData backups.
"""
from __future__ import annotations
import math
from datetime import datetime, timezone
from urllib.parse import urlsplit

KINDS=("Cuplu de strângere","Locație componentă","Schemă electrică",
       "Siguranță / releu","Conector / pinout","Fluid / capacitate",
       "Diagnosticare / test","Interval întreținere","Altă informație")
MAX_TEXT=2000

def ensure_schema(store):
    store.db.executescript("""
      CREATE TABLE IF NOT EXISTS workshop_facts(
        id INTEGER PRIMARY KEY,
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        system TEXT NOT NULL,
        component TEXT NOT NULL,
        operation TEXT NOT NULL DEFAULT '',
        value TEXT NOT NULL DEFAULT '',
        unit TEXT NOT NULL DEFAULT '',
        stages TEXT NOT NULL DEFAULT '',
        conditions TEXT NOT NULL DEFAULT '',
        component_location TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        source_name TEXT NOT NULL,
        source_url TEXT NOT NULL DEFAULT '',
        market TEXT NOT NULL DEFAULT '',
        applicability TEXT NOT NULL DEFAULT '',
        attachment_id INTEGER REFERENCES attachments(id) ON DELETE SET NULL,
        page_number INTEGER,
        updated_utc TEXT NOT NULL,
        CHECK (page_number IS NULL OR page_number >= 1)
      );
      CREATE INDEX IF NOT EXISTS idx_workshop_facts_vehicle
        ON workshop_facts(vehicle_id,kind,system,component);
      CREATE TABLE IF NOT EXISTS diagram_markers(
        id INTEGER PRIMARY KEY,
        attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
        page_number INTEGER NOT NULL DEFAULT 1 CHECK(page_number>=1),
        x REAL NOT NULL CHECK(x>=0 AND x<=1),
        y REAL NOT NULL CHECK(y>=0 AND y<=1),
        label TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        fact_id INTEGER REFERENCES workshop_facts(id) ON DELETE SET NULL
      );
      CREATE INDEX IF NOT EXISTS idx_diagram_markers_page
        ON diagram_markers(attachment_id,page_number);
    """)
    store.db.commit()

def _text(v,label,required=False,limit=MAX_TEXT):
    if not isinstance(v,str):raise ValueError(label+" invalid")
    v=v.strip()
    if required and not v:raise ValueError(label+" obligatoriu")
    if len(v)>limit or any(ord(c)<32 and c not in "\n\t" for c in v):
        raise ValueError(label+" prea lung sau conținut invalid")
    return v

def _url(v):
    v=_text(v,"URL sursă",limit=1200)
    if not v:return v
    u=urlsplit(v)
    try:port=u.port
    except ValueError as e:raise ValueError("Port sursă invalid") from e
    if u.scheme!="https" or not u.hostname or u.username or u.password or port not in (None,443):
        raise ValueError("Sursa trebuie să fie un URL HTTPS public")
    if u.hostname in ("localhost","127.0.0.1","::1") or u.hostname.endswith(".local"):
        raise ValueError("URL local interzis")
    return v

def _vehicle(store,vid):
    if isinstance(vid,bool) or not isinstance(vid,int):
        raise ValueError("Vehicul invalid")
    if store.db.execute("SELECT 1 FROM vehicles WHERE id=?",(vid,)).fetchone() is None:
        raise ValueError("Vehicul inexistent")

def _attachment(store,vid,attachment_id):
    if attachment_id in (None,""):return None
    if isinstance(attachment_id,bool):
        raise ValueError("Atașament invalid")
    try:attachment_id=int(attachment_id)
    except (ValueError,TypeError) as e:raise ValueError("Atașament invalid") from e
    row=store.db.execute("""SELECT a.id FROM attachments a
       JOIN articles ar ON ar.id=a.article_id
       WHERE a.id=? AND ar.vehicle_id=?""",(attachment_id,vid)).fetchone()
    if not row:raise ValueError("Documentul nu aparține motorizării selectate")
    return attachment_id

def record_fact(store,vehicle_id,kind,system,component,source_name,operation="",
                value="",unit="",stages="",conditions="",component_location="",
                notes="",source_url="",market="",applicability="",attachment_id=None,
                page_number=None,fact_id=None):
    ensure_schema(store);_vehicle(store,vehicle_id)
    if kind not in KINDS:raise ValueError("Tip de informație necunoscut")
    if kind=="Cuplu de strângere" and (not value.strip() or not unit.strip()):
        raise ValueError("Cuplul necesită valoare și unitate reale, cu sursă")
    if kind=="Locație componentă" and not component_location.strip():
        raise ValueError("Locația componentei nu a fost descrisă")
    if kind=="Schemă electrică" and attachment_id is None and not source_url:
        raise ValueError("Schema trebuie să aibă document sau link sursă")
    texts={
      "system":_text(system,"Sistem",True,130),
      "component":_text(component,"Componentă",True,180),
      "operation":_text(operation,"Operație",limit=300),
      "value":_text(value,"Valoare",limit=130),
      "unit":_text(unit,"Unitate",limit=40),
      "stages":_text(stages,"Etape / unghi / secvență",limit=900),
      "conditions":_text(conditions,"Condiții",limit=900),
      "component_location":_text(component_location,"Locație",limit=1000),
      "notes":_text(notes,"Observații",limit=MAX_TEXT),
      "source_name":_text(source_name,"Sursă",True,300),
      "source_url":_url(source_url),
      "market":_text(market,"Piață",limit=120),
      "applicability":_text(applicability,"Aplicabilitate",limit=600)
    }
    attached=_attachment(store,vehicle_id,attachment_id)
    if page_number not in (None,""):
        try:page_number=int(page_number)
        except (ValueError,TypeError) as e:raise ValueError("Pagina invalidă") from e
        if page_number<1 or attached is None:raise ValueError("Pagina necesită un document atașat")
    else:page_number=None
    fields=("vehicle_id","kind","system","component","operation","value","unit",
            "stages","conditions","component_location","notes","source_name",
            "source_url","market","applicability","attachment_id","page_number","updated_utc")
    vals=(vehicle_id,kind,*(texts[key] for key in fields[2:15]),
          attached,page_number,datetime.now(timezone.utc).isoformat())
    if fact_id is not None:
        old=store.db.execute("SELECT vehicle_id FROM workshop_facts WHERE id=?",(fact_id,)).fetchone()
        if not old or old[0]!=vehicle_id:raise ValueError("Informația aparține altui vehicul")
    with store.db:
        if fact_id is None:
            marks=",".join("?" for _ in fields)
            sql="INSERT INTO workshop_facts("+",".join(fields)+") VALUES("+marks+")"
            return store.db.execute(sql,vals).lastrowid
        else:
            updates=",".join(k+"=?" for k in fields[1:])
            store.db.execute("UPDATE workshop_facts SET "+updates+" WHERE id=?",
                             (*vals[1:],fact_id))
            return fact_id

def list_facts(store,vehicle_id=None,kind="",search=""):
    ensure_schema(store)
    sql="""SELECT f.*,v.make,v.model,v.engine,v.years,v.variant
       FROM workshop_facts f JOIN vehicles v ON v.id=f.vehicle_id WHERE 1=1"""
    args=[]
    if vehicle_id is not None:_vehicle(store,vehicle_id);sql+=" AND f.vehicle_id=?";args.append(vehicle_id)
    if kind:
        if kind not in KINDS:raise ValueError("Tip invalid")
        sql+=" AND f.kind=?";args.append(kind)
    if search:
        term=_text(search,"Căutare",limit=160)
        q="%"+term.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")+"%"
        sql+=(r""" AND (f.system LIKE ? ESCAPE '\' OR f.component LIKE ? ESCAPE '\'
          OR f.operation LIKE ? ESCAPE '\' OR f.value LIKE ? ESCAPE '\'
          OR f.component_location LIKE ? ESCAPE '\' OR f.notes LIKE ? ESCAPE '\'
          OR f.source_name LIKE ? ESCAPE '\')""")
        args.extend([q]*7)
    return store.db.execute(sql+" ORDER BY v.make,v.model,f.kind,f.system,f.component,f.id",args).fetchall()

def delete_fact(store,vehicle_id,fact_id):
    _vehicle(store,vehicle_id)
    with store.db:
        row=store.db.execute("DELETE FROM workshop_facts WHERE id=? AND vehicle_id=?",
                             (fact_id,vehicle_id))
        if not row.rowcount:raise ValueError("Informație inexistentă pentru vehicul")

def add_marker(store,vehicle_id,attachment_id,page_number,x,y,label,note="",fact_id=None):
    ensure_schema(store);_vehicle(store,vehicle_id)
    attachment_id=_attachment(store,vehicle_id,attachment_id)
    if attachment_id is None:raise ValueError("Document obligatoriu")
    try:
        page_number=int(page_number);x=float(x);y=float(y)
    except (TypeError,ValueError) as e:raise ValueError("Poziție invalidă") from e
    if page_number<1 or not(math.isfinite(x) and math.isfinite(y) and 0<=x<=1 and 0<=y<=1):
        raise ValueError("Coordonate relative invalide")
    label=_text(label,"Etichetă marcaj",True,160)
    note=_text(note,"Notă marcaj",limit=800)
    if fact_id is not None:
        row=store.db.execute("SELECT vehicle_id FROM workshop_facts WHERE id=?",(fact_id,)).fetchone()
        if not row or row[0]!=vehicle_id:raise ValueError("Referință componentă din alt vehicul")
    with store.db:
        return store.db.execute("""INSERT INTO diagram_markers(
           attachment_id,vehicle_id,page_number,x,y,label,note,fact_id)
           VALUES(?,?,?,?,?,?,?,?)""",
           (attachment_id,vehicle_id,page_number,x,y,label,note,fact_id)).lastrowid

def list_markers(store,vehicle_id,attachment_id,page_number=1):
    _vehicle(store,vehicle_id);_attachment(store,vehicle_id,attachment_id)
    return store.db.execute("""SELECT m.* FROM diagram_markers m
      WHERE m.vehicle_id=? AND m.attachment_id=? AND m.page_number=?
      ORDER BY m.id""",(vehicle_id,attachment_id,page_number)).fetchall()

def delete_marker(store,vehicle_id,marker_id):
    _vehicle(store,vehicle_id)
    with store.db:
        cursor=store.db.execute("DELETE FROM diagram_markers WHERE id=? AND vehicle_id=?",
                                (marker_id,vehicle_id))
        if not cursor.rowcount:raise ValueError("Marcaj inexistent")
