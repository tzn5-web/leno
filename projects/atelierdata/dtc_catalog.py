"""AtelierData: evidence-based vehicle-specific DTC reference catalogue.

This module stores user-supplied/licensed data only. No DTC definitions are inferred
from code patterns. It never connects to a vehicle, clears codes or changes ECUs.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path

DTC_PATTERN = re.compile(r"^[PBCU][0-9A-F]{4}$")
MAX_IMPORT_BYTES = 16 * 1024 * 1024
MAX_ROWS = 20000
DTC_FIELDS = ("code", "system", "title", "symptoms", "possible_causes",
              "checks", "notes", "source")


def _clean(value, label, length, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{label}: text expected")
    value = value.strip()
    if "\x00" in value or len(value) > length or (required and not value):
        raise ValueError(f"{label}: missing/invalid value")
    return value


def _dtc_data(record):
    if not isinstance(record, dict):
        raise ValueError("DTC record must be an object")
    code = _clean(record.get("code", "").upper() if isinstance(record.get("code", ""),str)
                  else record.get("code"), "code", 5, True)
    if not DTC_PATTERN.fullmatch(code):
        raise ValueError("DTC format must be P/B/C/U followed by four hexadecimal characters")
    return (
        code,
        _clean(record.get("system"), "system", 140, True),
        _clean(record.get("title"), "title", 250, True),
        _clean(record.get("symptoms"), "symptoms", 5000),
        _clean(record.get("possible_causes"), "possible_causes", 5000),
        _clean(record.get("checks"), "checks", 12000),
        _clean(record.get("notes"), "notes", 5000),
        _clean(record.get("source"), "source", 500, True)
    )


def ensure_schema(store):
    store.db.executescript("""
    CREATE TABLE IF NOT EXISTS dtc_entries(
        id INTEGER PRIMARY KEY,
        vehicle_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        system TEXT NOT NULL,
        title TEXT NOT NULL,
        symptoms TEXT NOT NULL DEFAULT '',
        possible_causes TEXT NOT NULL DEFAULT '',
        checks TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL,
        procedure_id INTEGER,
        article_id INTEGER,
        FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
        FOREIGN KEY(procedure_id) REFERENCES procedures(id) ON DELETE SET NULL,
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE SET NULL,
        UNIQUE(vehicle_id,code,source)
    );
    CREATE INDEX IF NOT EXISTS idx_dtc_vehicle_code
        ON dtc_entries(vehicle_id,code,system);
    """)
    store.db.commit()


def _validate_links(store, vehicle_id, procedure_id=None, article_id=None):
    if store.db.execute("SELECT 1 FROM vehicles WHERE id=?", (vehicle_id,)).fetchone() is None:
        raise ValueError("Vehicle not found")
    for target, table in ((procedure_id, "procedures"), (article_id, "articles")):
        if target is None or target == "":
            continue
        if not isinstance(target, int) or isinstance(target, bool) or target <= 0:
            raise ValueError("Document reference must be a positive integer")
        row = store.db.execute(f"SELECT vehicle_id FROM {table} WHERE id=?",(target,)).fetchone()
        if row is None or row[0] != vehicle_id:
            raise ValueError("Reference belongs to a different vehicle or does not exist")


def add_dtc(store, vehicle_id, code, system, title, symptoms="",
            possible_causes="", checks="", notes="", source="",
            procedure_id=None, article_id=None):
    data = _dtc_data(locals())
    _validate_links(store, vehicle_id, procedure_id, article_id)
    try:
        cursor = store.db.execute(
            "INSERT INTO dtc_entries(vehicle_id,code,system,title,symptoms,"
            "possible_causes,checks,notes,source,procedure_id,article_id)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (vehicle_id, *data, procedure_id, article_id))
        store.db.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError("DTC already exists for this vehicle and source") from exc


def update_dtc(store, entry_id, code, system, title, symptoms="",
               possible_causes="", checks="", notes="", source="",
               procedure_id=None, article_id=None):
    old = store.db.execute(
        "SELECT vehicle_id FROM dtc_entries WHERE id=?", (entry_id,)).fetchone()
    if old is None:
        raise ValueError("DTC entry not found")
    data = _dtc_data(locals())
    _validate_links(store, old["vehicle_id"], procedure_id, article_id)
    try:
        cursor = store.db.execute(
            "UPDATE dtc_entries SET code=?,system=?,title=?,symptoms=?,"
            "possible_causes=?,checks=?,notes=?,source=?,procedure_id=?,article_id=? "
            "WHERE id=?", (*data, procedure_id, article_id, entry_id))
        if not cursor.rowcount:
            raise ValueError("DTC entry not found")
        store.db.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError("DTC already exists for this vehicle and source") from exc


def delete_dtc(store, entry_id):
    store.db.execute("DELETE FROM dtc_entries WHERE id=?", (entry_id,))
    store.db.commit()


def get_dtc(store, entry_id):
    return store.db.execute(
        "SELECT * FROM dtc_entries WHERE id=?", (entry_id,)).fetchone()


def list_dtc(store, vehicle_id=None, search=""):
    query = ("SELECT d.*,v.make,v.model,v.engine, "
             "p.title AS procedure_title,a.title AS article_title "
             "FROM dtc_entries d "
             "JOIN vehicles v ON v.id=d.vehicle_id "
             "LEFT JOIN procedures p ON p.id=d.procedure_id "
             "LEFT JOIN articles a ON a.id=d.article_id WHERE 1=1")
    args = []
    if vehicle_id is not None:
        query += " AND d.vehicle_id=?"
        args.append(vehicle_id)
    if search:
        pattern = "%" + search + "%"
        query += (" AND (d.code LIKE ? OR d.system LIKE ? OR d.title LIKE ? "
                  "OR d.symptoms LIKE ? OR d.possible_causes LIKE ? "
                  "OR d.checks LIKE ? OR d.source LIKE ?)")
        args.extend([pattern] * 7)
    return store.db.execute(query+" ORDER BY d.code,d.system,d.title,d.id",args).fetchall()


def dtc_text(store, entry_id):
    row = next((r for r in list_dtc(store) if r["id"] == entry_id),None)
    if row is None:
        raise ValueError("DTC entry not found")
    chunks = [
        f"{row['code']} — {row['title']}",f"SISTEM: {row['system']}",
        f"VEHICUL: {row['make']} {row['model']} {row['engine']}",
        f"SURSĂ: {row['source']}",
    ]
    for heading,key in (("SIMPTOME", "symptoms"),
                        ("CAUZE POSIBILE", "possible_causes"),
                        ("VERIFICĂRI DOCUMENTATE", "checks"),
                        ("NOTE", "notes")):
        if row[key]:
            chunks.append(f"{heading}:\n{row[key]}")
    if row["procedure_title"]:
        chunks.append("PROCEDURĂ ASOCIATĂ: "+row["procedure_title"])
    if row["article_title"]:
        chunks.append("DOCUMENT ASOCIAT: "+row["article_title"])
    chunks.append("Referință documentară. Nu transmite comenzi OBD și nu șterge erori.")
    return "\n\n".join(chunks)


def _load_records(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError("Missing DTC import file or size above 16 MiB")
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
    elif path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = payload.get("records") if isinstance(payload,dict) else payload
        if isinstance(payload,dict) and payload.get("schema") not in (None, "atelierdata-dtc-v1"):
            raise ValueError("Unknown DTC import schema")
    else:
        raise ValueError("DTC import requires CSV or JSON")
    if not isinstance(rows,list) or len(rows) > MAX_ROWS:
        raise ValueError("DTC import expects at most 20000 records")
    result=[]
    for index, record in enumerate(rows,1):
        try:
            vehicle=tuple(_clean(record.get(k), k, 130, required=k in ("make","model"))
                          for k in ("make","model","engine","years","fuel","variant"))
            data = _dtc_data(record)
            result.append((vehicle,data))
        except (ValueError, AttributeError) as exc:
            raise ValueError(f"DTC row {index}: {exc}") from exc
    return result


def import_dtc(store,path):
    rows=_load_records(path)
    cache={}
    created=duplicates=0
    try:
        store.db.execute("BEGIN IMMEDIATE")
        for vehicle,data in rows:
            if vehicle not in cache:
                match=store.db.execute(
                    "SELECT id FROM vehicles WHERE make=? AND model=? AND engine=? AND "
                    "years=? AND fuel=? AND variant=?",vehicle).fetchone()
                if match:cache[vehicle]=match[0]
                else:
                    cursor=store.db.execute(
                        "INSERT INTO vehicles(make,model,engine,years,fuel,variant)"
                        " VALUES(?,?,?,?,?,?)",vehicle)
                    cache[vehicle]=cursor.lastrowid
            cursor=store.db.execute(
                "INSERT OR IGNORE INTO dtc_entries(vehicle_id,code,system,title,symptoms,"
                "possible_causes,checks,notes,source) VALUES(?,?,?,?,?,?,?,?,?)",
                (cache[vehicle], *data))
            if cursor.rowcount:created+=1
            else:duplicates+=1
        store.db.commit()
    except BaseException:
        store.db.rollback()
        raise
    return {"inserted":created,"duplicates":duplicates,"processed":len(rows)}


def export_dtc(store,path):
    dest=Path(path)
    if dest.resolve()==store.path.resolve():
        raise ValueError("Cannot replace the SQLite database")
    dest.parent.mkdir(parents=True,exist_ok=True)
    keys=("make","model","engine","years","fuel","variant",*DTC_FIELDS)
    # Query vehicle directly to preserve exact metadata in round-trips.
    records=[dict(zip(keys, row)) for row in store.db.execute(
        "SELECT v.make,v.model,v.engine,v.years,v.fuel,v.variant,"
        "d.code,d.system,d.title,d.symptoms,d.possible_causes,d.checks,d.notes,d.source "
        "FROM dtc_entries d JOIN vehicles v ON v.id=d.vehicle_id ORDER BY v.make,v.model,d.code,d.id")]
    payload={"schema":"atelierdata-dtc-v1","scope":"user-provided or licensed entries only",
             "records":records}
    fd,tmp=tempfile.mkstemp(prefix=".atelierdata-dtc-",dir=str(dest.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(payload,stream,indent=2,ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return len(records)
