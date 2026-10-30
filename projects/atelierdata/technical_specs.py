"""AtelierData structured workshop specifications — user-licensed data only.

No fabricated automotive values, no proprietary IDF decoding, no network calls.
"""
from __future__ import annotations
import csv
import json
import os
import sqlite3
import tempfile
from pathlib import Path

FIELDS=("make","model","engine","years","fuel","variant",
        "system","parameter","value","unit","conditions","source")
MAX_IMPORT_BYTES=20*1024*1024
MAX_ROWS=25000

def ensure_schema(store):
    store.db.executescript("""
    CREATE TABLE IF NOT EXISTS technical_specs(
      id INTEGER PRIMARY KEY,
      vehicle_id INTEGER NOT NULL,
      system TEXT NOT NULL,
      parameter TEXT NOT NULL,
      value TEXT NOT NULL,
      unit TEXT NOT NULL DEFAULT '',
      conditions TEXT NOT NULL DEFAULT '',
      source TEXT NOT NULL DEFAULT '',
      FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_specs_vehicle_system ON technical_specs(vehicle_id,system,parameter);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_specs_unique
    ON technical_specs(vehicle_id,system,parameter,value,unit,conditions,source);
    """)
    store.db.commit()

def _field(value,label,max_length,required=False):
    if value is None:
        value=""
    if not isinstance(value,(str,int,float)):
        raise ValueError("Valoare invalidă: "+label)
    text=str(value).strip()
    if required and not text:
        raise ValueError("Câmp obligatoriu: "+label)
    if len(text)>max_length or '\0' in text:
        raise ValueError("Câmp prea lung sau invalid: "+label)
    return text

def _spec_fields(row):
    return (
       _field(row.get("system"),"system",120,True),
       _field(row.get("parameter"),"parameter",160,True),
       _field(row.get("value"),"value",240,True),
       _field(row.get("unit"),"unit",48),
       _field(row.get("conditions"),"conditions",1000),
       _field(row.get("source"),"source",350,True))

def _vehicle_fields(row):
    return (
        _field(row.get("make"),"make",100,True),
        _field(row.get("model"),"model",100,True),
        _field(row.get("engine"),"engine",100),
        _field(row.get("years"),"years",100),
        _field(row.get("fuel"),"fuel",100),
        _field(row.get("variant"),"variant",100))

def add_spec(store,vehicle_id,system,parameter,value,unit="",conditions="",source=""):
    spec=_spec_fields(locals())
    if store.db.execute("SELECT id FROM vehicles WHERE id=?",(vehicle_id,)).fetchone() is None:
        raise ValueError("Vehicul inexistent")
    cursor=store.db.execute(
      "INSERT OR IGNORE INTO technical_specs(vehicle_id,system,parameter,value,unit,conditions,source)"
      " VALUES(?,?,?,?,?,?,?)",(vehicle_id,*spec))
    store.db.commit()
    if cursor.rowcount:
        return cursor.lastrowid
    duplicate=store.db.execute(
      "SELECT id FROM technical_specs WHERE vehicle_id=? AND system=? AND parameter=? "
      "AND value=? AND unit=? AND conditions=? AND source=?",(vehicle_id,*spec)).fetchone()
    return duplicate[0]

def update_spec(store,spec_id,system,parameter,value,unit="",conditions="",source=""):
    spec=_spec_fields(locals())
    try:
        cursor=store.db.execute("UPDATE technical_specs SET system=?,parameter=?,value=?,unit=?,"
            "conditions=?,source=? WHERE id=?",(*spec,spec_id))
    except sqlite3.IntegrityError as exc:
        raise ValueError("Specificație duplicată") from exc
    if not cursor.rowcount:
        raise ValueError("Specificație inexistentă")
    store.db.commit()

def remove_spec(store,spec_id):
    store.db.execute("DELETE FROM technical_specs WHERE id=?",(spec_id,))
    store.db.commit()

def get_spec(store,spec_id):
    return store.db.execute("SELECT * FROM technical_specs WHERE id=?",(spec_id,)).fetchone()

def list_specs(store,vehicle_id=None,search="",system=None):
    query=("SELECT s.*,v.make,v.model,v.engine,v.years,v.fuel,v.variant "
           "FROM technical_specs s JOIN vehicles v ON v.id=s.vehicle_id WHERE 1=1")
    args=[]
    if vehicle_id is not None:
        query+=" AND s.vehicle_id=?";args.append(vehicle_id)
    if system:
        query+=" AND s.system=?";args.append(system)
    if search:
        q="%"+search+"%"
        query+=" AND (s.system LIKE ? OR s.parameter LIKE ? OR s.value LIKE ? OR s.conditions LIKE ?)"
        args.extend([q]*4)
    return store.db.execute(query+" ORDER BY v.make,v.model,v.engine,s.system,s.parameter,s.id",args).fetchall()

def _load_input(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>MAX_IMPORT_BYTES:
        raise ValueError("Fișier lipsă sau mai mare de 20 MiB")
    if path.suffix.lower()==".csv":
        with path.open("r",encoding="utf-8-sig",newline="") as inp:
            rows=list(csv.DictReader(inp))
    elif path.suffix.lower()==".json":
        payload=json.loads(path.read_text(encoding="utf-8-sig"))
        rows=payload.get("specifications") if isinstance(payload,dict) else payload
        if isinstance(payload,dict) and payload.get("schema") not in (None,"atelierdata-specifications-v1"):
            raise ValueError("Versiune schemă necunoscută")
    else: raise ValueError("Format permis: CSV sau JSON")
    if not isinstance(rows,list) or len(rows)>MAX_ROWS:
        raise ValueError("Lista trebuie să aibă maximum 25000 de intrări")
    validated=[]
    for rownumber,row in enumerate(rows,1):
        if not isinstance(row,dict):raise ValueError(f"Rând invalid: {rownumber}")
        try:validated.append((_vehicle_fields(row),_spec_fields(row)))
        except ValueError as exc:raise ValueError(f"Rândul {rownumber}: {exc}") from exc
    return validated

def import_specs(store,path):
    """All-or-nothing import with deduplication; no partial writes on bad inputs."""
    rows=_load_input(path)
    cache={}
    inserted=duplicates=0
    try:
        store.db.execute("BEGIN IMMEDIATE")
        for vehicle,spec in rows:
            if vehicle not in cache:
                old=store.db.execute(
                  "SELECT id FROM vehicles WHERE make=? AND model=? AND engine=? "
                  "AND years=? AND fuel=? AND variant=?",vehicle).fetchone()
                if old:cache[vehicle]=old[0]
                else:
                    cur=store.db.execute("INSERT INTO vehicles(make,model,engine,years,fuel,variant)"
                        " VALUES(?,?,?,?,?,?)",vehicle)
                    cache[vehicle]=cur.lastrowid
            cursor=store.db.execute(
              "INSERT OR IGNORE INTO technical_specs(vehicle_id,system,parameter,value,unit,conditions,source)"
              " VALUES(?,?,?,?,?,?,?)",(cache[vehicle],*spec))
            if cursor.rowcount:inserted+=1
            else:duplicates+=1
        store.db.commit()
    except BaseException:
        store.db.rollback()
        raise
    return {"inserted":inserted,"duplicates":duplicates,"processed":len(rows)}

def export_specs(store,path):
    """Atomic JSON export of manually authored/licensed entries, including provenance."""
    destination=Path(path)
    if destination.resolve()==store.path.resolve():
        raise ValueError("Nu suprascrie baza SQLite")
    destination.parent.mkdir(parents=True,exist_ok=True)
    rows=[{name:row[name] for name in FIELDS} for row in list_specs(store)]
    payload={"schema":"atelierdata-specifications-v1",
             "scope":"user-provided technical reference data only",
             "specifications":rows}
    fd,temporary=tempfile.mkstemp(prefix=".atelierdata-specs-",dir=str(destination.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as output:
            json.dump(payload,output,ensure_ascii=False,indent=2)
            output.flush();os.fsync(output.fileno())
        os.replace(temporary,destination)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    return len(rows)
