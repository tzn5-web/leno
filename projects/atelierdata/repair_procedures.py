"""AtelierData repair procedures with ordered steps and verified document references.

All content is entered by a user or obtained under an appropriate licence.
No OEM/Autodata data, repair values or techniques are included.
"""
from __future__ import annotations

import sqlite3

MAX_SYSTEM=120
MAX_TITLE=180
MAX_SUMMARY=4000
MAX_WARNING=2000
MAX_INSTRUCTION=12000
MAX_SOURCE=500


def _text(value, label, limit, required=False):
    if not isinstance(value, str):
        raise ValueError(f"{label}: text required")
    value = value.strip()
    if (required and not value) or len(value) > limit or "\0" in value:
        raise ValueError(f"{label}: invalid length or content")
    return value


def ensure_schema(store):
    store.db.executescript("""
    CREATE TABLE IF NOT EXISTS procedures(
      id INTEGER PRIMARY KEY,
      vehicle_id INTEGER NOT NULL,
      system TEXT NOT NULL,
      title TEXT NOT NULL,
      summary TEXT NOT NULL DEFAULT '',
      precautions TEXT NOT NULL DEFAULT '',
      source TEXT NOT NULL,
      FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_procedures_vehicle_system
      ON procedures(vehicle_id, system, title);
    CREATE TABLE IF NOT EXISTS procedure_steps(
      id INTEGER PRIMARY KEY,
      procedure_id INTEGER NOT NULL,
      step_number INTEGER NOT NULL CHECK(step_number > 0),
      instruction TEXT NOT NULL,
      safety_note TEXT NOT NULL DEFAULT '',
      article_id INTEGER,
      FOREIGN KEY(procedure_id) REFERENCES procedures(id) ON DELETE CASCADE,
      FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE SET NULL,
      UNIQUE(procedure_id,step_number)
    );
    CREATE INDEX IF NOT EXISTS idx_steps_procedure ON procedure_steps(procedure_id,step_number);
    """)
    store.db.commit()


def create_procedure(store, vehicle_id, system, title, summary="", precautions="", source=""):
    fields = (_text(system,"system",MAX_SYSTEM,True),
              _text(title,"title",MAX_TITLE,True),
              _text(summary,"summary",MAX_SUMMARY),
              _text(precautions,"precautions",MAX_WARNING),
              _text(source,"source",MAX_SOURCE,True))
    if store.db.execute("SELECT 1 FROM vehicles WHERE id=?",(vehicle_id,)).fetchone() is None:
        raise ValueError("Vehicle does not exist")
    cur=store.db.execute("INSERT INTO procedures(vehicle_id,system,title,summary,precautions,source)"
        " VALUES(?,?,?,?,?,?)",(vehicle_id,*fields))
    store.db.commit()
    return cur.lastrowid


def update_procedure(store, procedure_id, system, title, summary="",precautions="",source=""):
    fields=(_text(system,"system",MAX_SYSTEM,True),
            _text(title,"title",MAX_TITLE,True),
            _text(summary,"summary",MAX_SUMMARY),
            _text(precautions,"precautions",MAX_WARNING),
            _text(source,"source",MAX_SOURCE,True))
    row=store.db.execute("UPDATE procedures SET system=?,title=?,summary=?,precautions=?,source=?"
                         " WHERE id=?",(*fields,procedure_id))
    if row.rowcount == 0:
        raise ValueError("Procedure does not exist")
    store.db.commit()


def list_procedures(store,vehicle_id=None,search=""):
    sql=("SELECT p.*,v.make,v.model,v.engine FROM procedures p "
         "JOIN vehicles v ON v.id=p.vehicle_id WHERE 1=1")
    args=[]
    if vehicle_id is not None:
        sql+=" AND p.vehicle_id=?";args.append(vehicle_id)
    if search:
        sql+=(" AND (p.title LIKE ? OR p.system LIKE ? OR p.summary LIKE ?"
              " OR p.precautions LIKE ? OR p.source LIKE ?"
              " OR EXISTS (SELECT 1 FROM procedure_steps s"
              " LEFT JOIN articles a ON a.id=s.article_id"
              " WHERE s.procedure_id=p.id AND (s.instruction LIKE ?"
              " OR s.safety_note LIKE ? OR a.title LIKE ?)))")
        args.extend(["%"+search+"%"]*8)
    return store.db.execute(sql+" ORDER BY v.make,v.model,p.system,p.title,p.id",args).fetchall()



def list_reference_articles(store, procedure_id, search=""):
    """Documents available to a step, scoped strictly to the procedure's vehicle.

    The returned data are only user-entered article metadata; no remote content.
    Search treats %, _ and backslash as literal characters.
    """
    if get_procedure(store, procedure_id) is None:
        raise ValueError("Procedure does not exist")
    if not isinstance(search, str) or len(search) > 200 or "\0" in search:
        raise ValueError("Invalid document search")
    query = ("SELECT a.id,a.vehicle_id,a.category,a.title,a.source "
             "FROM articles a JOIN procedures p ON p.vehicle_id=a.vehicle_id "
             "WHERE p.id=?")
    args = [procedure_id]
    if search:
        pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query += (" AND (a.title LIKE ? ESCAPE '\\' OR a.category LIKE ? ESCAPE '\\'"
                  " OR a.source LIKE ? ESCAPE '\\')")
        args.extend((pattern, pattern, pattern))
    return store.db.execute(query + " ORDER BY a.category,a.title,a.id", args).fetchall()


def get_procedure(store,pid):
    return store.db.execute("SELECT * FROM procedures WHERE id=?",(pid,)).fetchone()


def delete_procedure(store,pid):
    store.db.execute("DELETE FROM procedures WHERE id=?",(pid,))
    store.db.commit()


def list_steps(store,procedure_id):
    return store.db.execute("SELECT s.*,a.title AS reference_title FROM procedure_steps s "
        "LEFT JOIN articles a ON a.id=s.article_id "
        "WHERE s.procedure_id=? ORDER BY s.step_number,s.id",(procedure_id,)).fetchall()


def _article_reference(store, procedure_id, article_id):
    if article_id in (None,""):
        return None
    try:
        article_id=int(article_id)
    except (TypeError,ValueError) as exc:
        raise ValueError("Article reference must be an integer") from exc
    parent=store.db.execute("SELECT vehicle_id FROM procedures WHERE id=?",(procedure_id,)).fetchone()
    if parent is None:
        raise ValueError("Procedure does not exist")
    article=store.db.execute("SELECT vehicle_id FROM articles WHERE id=?",(article_id,)).fetchone()
    if article is None or article[0] != parent[0]:
        raise ValueError("Linked article must belong to the same vehicle")
    return article_id


def _renumber(store,procedure_id,ordered_ids):
    # Stage at unused positive indices; CHECK(step_number > 0) remains satisfied.
    row=store.db.execute("SELECT COALESCE(MAX(step_number),0) FROM procedure_steps "
                         "WHERE procedure_id=?",(procedure_id,)).fetchone()
    offset=row[0]+len(ordered_ids)+1
    for idx,sid in enumerate(ordered_ids,1):
        store.db.execute("UPDATE procedure_steps SET step_number=? "
                         "WHERE procedure_id=? AND id=?",(offset+idx,procedure_id,sid))
    for idx,sid in enumerate(ordered_ids,1):
        store.db.execute("UPDATE procedure_steps SET step_number=? "
                         "WHERE procedure_id=? AND id=?",(idx,procedure_id,sid))


def add_step(store,procedure_id,instruction,safety_note="",article_id=None,position=None):
    instruction=_text(instruction,"instruction",MAX_INSTRUCTION,True)
    safety_note=_text(safety_note,"safety note",MAX_WARNING)
    ref=_article_reference(store,procedure_id,article_id)
    current=[s["id"] for s in list_steps(store,procedure_id)]
    if position is None:
        position=len(current)+1
    if not isinstance(position,int) or not 1 <= position <= len(current)+1:
        raise ValueError("Invalid step position")
    try:
        store.db.execute("BEGIN IMMEDIATE")
        cursor=store.db.execute(
            "INSERT INTO procedure_steps(procedure_id,step_number,instruction,safety_note,article_id)"
            " VALUES(?,?,?,?,?)",(procedure_id,len(current)+1,instruction,safety_note,ref))
        new_id=cursor.lastrowid
        current.insert(position-1,new_id)
        _renumber(store,procedure_id,current)
        store.db.commit()
        return new_id
    except BaseException:
        store.db.rollback()
        raise


def update_step(store,step_id,instruction,safety_note="",article_id=None):
    old=store.db.execute("SELECT * FROM procedure_steps WHERE id=?",(step_id,)).fetchone()
    if old is None:
        raise ValueError("Step does not exist")
    fields=(_text(instruction,"instruction",MAX_INSTRUCTION,True),
            _text(safety_note,"safety note",MAX_WARNING),
            _article_reference(store,old["procedure_id"],article_id))
    store.db.execute("UPDATE procedure_steps SET instruction=?,safety_note=?,article_id=? "
                     "WHERE id=?",(*fields,step_id))
    store.db.commit()


def delete_step(store,step_id):
    old=store.db.execute("SELECT procedure_id FROM procedure_steps WHERE id=?",(step_id,)).fetchone()
    if old is None:
        return
    pid=old[0]
    try:
        store.db.execute("BEGIN IMMEDIATE")
        store.db.execute("DELETE FROM procedure_steps WHERE id=?",(step_id,))
        _renumber(store,pid,[s["id"] for s in list_steps(store,pid)])
        store.db.commit()
    except BaseException:
        store.db.rollback()
        raise


def move_step(store,step_id,delta):
    if delta not in (-1,1):
        raise ValueError("Direction must be +1 or -1")
    old=store.db.execute("SELECT procedure_id FROM procedure_steps WHERE id=?",(step_id,)).fetchone()
    if old is None:
        raise ValueError("Step does not exist")
    pid=old[0]
    ids=[s["id"] for s in list_steps(store,pid)]
    pos=ids.index(step_id)
    target=pos+delta
    if target<0 or target>=len(ids):
        return False
    ids[pos],ids[target]=ids[target],ids[pos]
    try:
        store.db.execute("BEGIN IMMEDIATE")
        _renumber(store,pid,ids)
        store.db.commit()
    except BaseException:
        store.db.rollback()
        raise
    return True


def procedure_text(store,pid):
    p=get_procedure(store,pid)
    if p is None:
        raise ValueError("Procedure does not exist")
    header=f"{p['system']} — {p['title']}\nSURSĂ: {p['source']}"
    if p["summary"]:header+=f"\nREZUMAT: {p['summary']}"
    if p["precautions"]:header+=f"\nAVERTISMENT GENERAL: {p['precautions']}"
    steps=list_steps(store,pid)
    if not steps:
        return header+"\n\nNu există pași configurați."
    body=[]
    for step in steps:
        line=f"{step['step_number']}. {step['instruction']}"
        if step["safety_note"]:
            line+="\n    ATENȚIE: "+step["safety_note"]
        if step["reference_title"]:
            line+="\n    DOCUMENT ASOCIAT: "+step["reference_title"]
        body.append(line)
    return header+"\n\n"+"\n\n".join(body)
