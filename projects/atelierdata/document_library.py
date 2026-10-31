"""AtelierData: private, vehicle-scoped library for user-authorized workshop files.

Indexes existing managed attachments without copying or downloading anything.
Every stored file is linked to an exact vehicle row through its article, with
make/model/engine/year inherited from SQLite. File bytes stay under documents/
and are SHA256-checked by the pre-existing resolve_document() routine.

Recording a source or a license assertion is not independent verification of
permission, vehicle applicability, or technical correctness.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
import re

from atelierdata_extensions import attach_document, resolve_document

DOCUMENT_TYPES=("Manual de atelier","Procedură","Schemă electrică",
                "Buletin tehnic","Manual utilizare","Diagnosticare / DTC",
                "Specificații","Alt document")
ACCESS_RIGHTS=("neconfirmat","document_propriu","licenta_expresa",
               "domeniu_public","permisiune_scrisa")
MAX_TEXT=300

def ensure_schema(store):
    store.db.execute("""CREATE TABLE IF NOT EXISTS library_documents(
      attachment_id INTEGER PRIMARY KEY,
      document_type TEXT NOT NULL,
      display_title TEXT NOT NULL,
      source_name TEXT NOT NULL DEFAULT '',
      source_url TEXT NOT NULL DEFAULT '',
      language TEXT NOT NULL DEFAULT '',
      market TEXT NOT NULL DEFAULT '',
      revision TEXT NOT NULL DEFAULT '',
      rights_basis TEXT NOT NULL DEFAULT 'neconfirmat',
      applicability_note TEXT NOT NULL DEFAULT '',
      declared_at_utc TEXT NOT NULL,
      FOREIGN KEY(attachment_id) REFERENCES attachments(id) ON DELETE CASCADE
    )""")
    store.db.execute("""CREATE INDEX IF NOT EXISTS idx_library_kind
        ON library_documents(document_type,source_name)""")
    store.db.commit()

def _clean(text, label, required=False, limit=MAX_TEXT):
    if not isinstance(text,str):
        raise ValueError(label+" trebuie să fie text")
    value=text.strip()
    if len(value)>limit:
        raise ValueError(label+" este prea lung")
    if required and not value:
        raise ValueError(label+" este obligatoriu")
    if any(ord(c)<32 for c in value):
        raise ValueError(label+" conține caractere de control")
    return value

def _validate_url(value):
    url=_clean(value,"Link sursă",limit=1500)
    if not url:return ""
    obj=urlsplit(url)
    if (obj.scheme!="https" or not obj.hostname or obj.username or obj.password
            or obj.port not in (None,443) or obj.hostname.endswith(".local")
            or obj.hostname in ("localhost","127.0.0.1","::1")):
        raise ValueError("Permis doar link HTTPS public către sursă")
    return url

def document_attachment(store, attachment_id):
    row=store.db.execute("""SELECT att.id,att.path,art.id AS article_id,
          art.vehicle_id,art.title AS article_title,art.category,art.source AS article_source,
          v.make,v.model,v.engine,v.years,v.fuel,v.variant
          FROM attachments att
          JOIN articles art ON art.id=att.article_id
          JOIN vehicles v ON v.id=art.vehicle_id
          WHERE att.id=?""",(attachment_id,)).fetchone()
    if row is None:raise ValueError("Atașament inexistent")
    return row

def set_metadata(store, attachment_id, document_type, display_title,
                 source_name, source_url="", language="", market="",
                 revision="", rights_basis="neconfirmat", applicability_note=""):
    ensure_schema(store)
    attachment=document_attachment(store,attachment_id)
    if document_type not in DOCUMENT_TYPES:
        raise ValueError("Categorie document necunoscută")
    if rights_basis not in ACCESS_RIGHTS:
        raise ValueError("Bază juridică necunoscută")
    # Verify the attached file before indexing, even when only editing metadata.
    resolve_document(store,attachment_id)
    values=(
        attachment_id,document_type,
        _clean(display_title,"Titlu",required=True),
        _clean(source_name,"Proveniență",required=True),
        _validate_url(source_url),
        _clean(language,"Limbă"),_clean(market,"Piață"),
        _clean(revision,"Revizie"),
        rights_basis,_clean(applicability_note,"Aplicabilitate",limit=1000),
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    with store.db:
        store.db.execute("""INSERT INTO library_documents (
          attachment_id,document_type,display_title,source_name,source_url,language,
          market,revision,rights_basis,applicability_note,declared_at_utc)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(attachment_id) DO UPDATE SET
          document_type=excluded.document_type,display_title=excluded.display_title,
          source_name=excluded.source_name,source_url=excluded.source_url,
          language=excluded.language,market=excluded.market,
          revision=excluded.revision,rights_basis=excluded.rights_basis,
          applicability_note=excluded.applicability_note,
          declared_at_utc=excluded.declared_at_utc""",values)
    return attachment

def import_local_file(store, vehicle_id, source_path, category, title, source_name,
                      source_url="", language="", market="", revision="",
                      rights_basis="neconfirmat", applicability_note=""):
    """Explicit local user-selected import. No crawling or binary execution.

    Vehicle ID must pre-exist; the vehicle's engine/year are not inferred.
    """
    if not isinstance(vehicle_id,int) or isinstance(vehicle_id,bool):
        raise ValueError("Selectează un vehicul valid")
    row=store.db.execute("SELECT id FROM vehicles WHERE id=?",(vehicle_id,)).fetchone()
    if row is None:raise ValueError("Vehicul inexistent")
    category=_clean(category,"Categorie",required=True)
    title=_clean(title,"Titlu",required=True)
    source_name=_clean(source_name,"Proveniență",required=True)
    # Validate all metadata BEFORE creating any articles/files.
    if category not in DOCUMENT_TYPES:raise ValueError("Tip de document necunoscut")
    if rights_basis not in ACCESS_RIGHTS:raise ValueError("Drepturi neconfirmate")
    _validate_url(source_url)
    _clean(applicability_note,"Aplicabilitate",limit=1000)
    source_path=Path(source_path)
    if not source_path.is_file() or source_path.is_symlink():
        raise ValueError("Fișier local invalid")
    # Explicit confirmation is required in UI; this flag is a user declaration,
    # never a verified vendor license.
    if rights_basis=="neconfirmat":
        raise ValueError("Nu importa documente fără confirmarea dreptului de păstrare")
    aid=store.add_article(vehicle_id,category,title,
              "Document local atașat; consultă fișierul original verificat SHA256.",
              source_name)
    try:
        attachment_id=attach_document(store,aid,source_path)
        set_metadata(store,attachment_id,category,title,source_name,source_url,
                     language,market,revision,rights_basis,applicability_note)
        return attachment_id
    except Exception:
        store.delete_article(aid)
        raise

def list_library(store,make="",model="",engine="",year="",category="",query="",
                 rights_basis="",only_indexed=False):
    ensure_schema(store)
    sql="""SELECT att.id AS attachment_id,att.path,art.id AS article_id,
          v.id AS vehicle_id,v.make,v.model,v.engine,v.years,v.variant,
          art.title AS article_title,art.category AS article_category,
          art.source AS article_source,
          lib.document_type,lib.display_title,lib.source_name,lib.source_url,
          lib.language,lib.market,lib.revision,lib.rights_basis,
          lib.applicability_note,lib.declared_at_utc
          FROM attachments att
          JOIN articles art ON art.id=att.article_id
          JOIN vehicles v ON v.id=art.vehicle_id
          LEFT JOIN library_documents lib ON lib.attachment_id=att.id
          WHERE 1=1"""
    params=[]
    for column,value in (("v.make",make),("v.model",model),("v.engine",engine)):
        value=_clean(value,"Filtru")
        if value:
            sql+=" AND "+column+" = ? COLLATE NOCASE"
            params.append(value)
    if category:
        if category not in DOCUMENT_TYPES:raise ValueError("Categorie necunoscută")
        sql+=" AND COALESCE(lib.document_type,art.category)=?"
        params.append(category)
    if rights_basis:
        if rights_basis not in ACCESS_RIGHTS:raise ValueError("Drepturi necunoscute")
        sql+=" AND COALESCE(lib.rights_basis,'neconfirmat')=?"
        params.append(rights_basis)
    if only_indexed:sql+=" AND lib.attachment_id IS NOT NULL"
    q=_clean(query,"Căutare",limit=150)
    if q:
        # SQLite LIKE only folds ASCII case; this matches the Unicode-aware
        # procedure search and treats '%'/'_' as ordinary document text.
        # Bind the needle separately: never interpolate user input into SQL.
        store.db.create_function(
            "atelierdata_library_contains", 2,
            lambda value, needle: int(isinstance(value, str)
                                      and isinstance(needle, str)
                                      and needle.casefold() in value.casefold()),
            deterministic=True)
        # Search the provenance and edition metadata displayed by the GUI,
        # not only the document title. Old attachments without indexed metadata
        # remain searchable through their original article fields.
        sql+=(""" AND (atelierdata_library_contains(v.make, ?)
         OR atelierdata_library_contains(v.model, ?)
         OR atelierdata_library_contains(v.engine, ?)
         OR atelierdata_library_contains(art.title, ?)
         OR atelierdata_library_contains(art.category, ?)
         OR atelierdata_library_contains(art.source, ?)
         OR atelierdata_library_contains(lib.document_type, ?)
         OR atelierdata_library_contains(lib.display_title, ?)
         OR atelierdata_library_contains(lib.source_name, ?)
         OR atelierdata_library_contains(lib.source_url, ?)
         OR atelierdata_library_contains(lib.language, ?)
         OR atelierdata_library_contains(lib.market, ?)
         OR atelierdata_library_contains(lib.revision, ?)
         OR atelierdata_library_contains(lib.rights_basis, ?)
         OR atelierdata_library_contains(lib.applicability_note, ?))""")
        params.extend([q]*15)
    sql+=" ORDER BY v.make,v.model,v.engine,COALESCE(lib.display_title,art.title),att.id"
    rows=[dict(r) for r in store.db.execute(sql,params)]
    # A model year is not identical to a year range. Filter the vehicle's exact
    # saved year label or a simple year interval; do NOT claim applicability.
    year=_clean(year,"An",limit=16)
    if year:
        if not re.fullmatch(r"\d{4}",year):raise ValueError("Anul trebuie să fie YYYY")
        n=int(year)
        def matches(years):
            text=str(years or "").strip()
            if text==year:return True
            m=re.fullmatch(r"(\d{4})\s*[-–]\s*(\d{4})",text)
            return bool(m and int(m[1])<=n<=int(m[2]))
        rows=[x for x in rows if matches(x["years"])]
    return rows

def verified_library_file(store,attachment_id,vehicle_id=None):
    attachment=document_attachment(store,attachment_id)
    if vehicle_id is not None and attachment["vehicle_id"]!=vehicle_id:
        raise ValueError("Documentul nu aparține vehiculului selectat")
    return resolve_document(store,attachment_id)
