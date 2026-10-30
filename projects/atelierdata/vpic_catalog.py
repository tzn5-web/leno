"""NHTSA vPIC public make/model lookup, explicit import, offline SQLite cache.

Only vehicle names and model year are fetched. No VINs, plate numbers, engine data
or user documents are transmitted. No repair specifications are inferred.
Official endpoint: https://vpic.nhtsa.dot.gov/api/
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
import urllib.request

BASE="https://vpic.nhtsa.dot.gov/api/vehicles"
MAX_RESPONSE=2_000_000
MAX_ROWS=2500
MAKE_RE=re.compile(r"^[\w .&'()/-]{2,80}$",re.UNICODE)
SOURCE="NHTSA vPIC GetModelsForMakeYear — public vehicle identification data"

def valid_query(make,year):
    if not isinstance(make,str) or not MAKE_RE.fullmatch(make.strip()):
        raise ValueError("Marca este invalidă (2-80 caractere)")
    if isinstance(year,bool):
        raise ValueError("An invalid")
    try:year=int(year)
    except (ValueError,TypeError) as exc:raise ValueError("An invalid") from exc
    if not 1996<=year<=dt.datetime.now(dt.timezone.utc).year+1:
        raise ValueError("vPIC year outside supported interval 1996–next year")
    return make.strip(),year

def endpoint(make,year):
    make,year=valid_query(make,year)
    safe=urllib.parse.quote(make,safe="")
    return f"{BASE}/GetModelsForMakeYear/make/{safe}/modelyear/{year}?format=json"

def parse_response(raw,make,year):
    make,year=valid_query(make,year)
    if isinstance(raw,bytes):
        if len(raw)>MAX_RESPONSE:raise ValueError("Oversized API response")
        raw=raw.decode("utf-8")
    if isinstance(raw,str):
        if len(raw)>MAX_RESPONSE:raise ValueError("Oversized API response")
        raw=json.loads(raw)
    if not isinstance(raw,dict) or not isinstance(raw.get("Results"),list):
        raise ValueError("Invalid vPIC API response")
    if raw.get("Message") and ("error" in str(raw["Message"]).lower()):
        raise ValueError("vPIC API error: "+str(raw["Message"])[:180])
    result=raw["Results"]
    if len(result)>MAX_ROWS:raise ValueError("Too many results")
    models={}
    for item in result:
        if not isinstance(item,dict):continue
        actual_make=str(item.get("Make_Name") or "").strip()
        name=str(item.get("Model_Name") or "").strip()
        if actual_make.casefold()!=make.casefold() or not 1<=len(name)<=120:
            continue
        make_id=item.get("Make_ID")
        model_id=item.get("Model_ID")
        if not isinstance(make_id,int) or not isinstance(model_id,int):continue
        if make_id<=0 or model_id<=0:continue
        models[(make_id,model_id)]={"make_id":make_id,"make_name":actual_make,
                                   "model_id":model_id,"model_name":name,"model_year":year}
    return sorted(models.values(),key=lambda x:(x["model_name"].casefold(),x["model_id"]))

def fetch_models(make,year,fetcher=None):
    url=endpoint(make,year)
    if fetcher is not None:
        return parse_response(fetcher(url),make,year)
    request=urllib.request.Request(
        url,headers={"User-Agent":"AtelierData/0.2 (NHTSA-vPIC; public make-year lookup)",
                     "Accept":"application/json"})
    # Fixed, trusted URL; only a make and model year are sent.
    with urllib.request.urlopen(request,timeout=12) as response:
        if response.geturl().split("/")[2].lower()!="vpic.nhtsa.dot.gov":
            raise ValueError("Unexpected API redirect")
        raw=response.read(MAX_RESPONSE+1)
    return parse_response(raw,make,year)

def ensure_schema(store):
    store.db.executescript("""
    CREATE TABLE IF NOT EXISTS public_vehicle_models(
        make_id INTEGER NOT NULL,model_id INTEGER NOT NULL,
        make_name TEXT NOT NULL,model_name TEXT NOT NULL,
        model_year INTEGER NOT NULL,source TEXT NOT NULL,
        retrieved_utc TEXT NOT NULL,
        PRIMARY KEY(make_id,model_id,model_year));
    CREATE INDEX IF NOT EXISTS idx_public_models_lookup
      ON public_vehicle_models(make_name,model_year,model_name);
    """)
    store.db.commit()

def cache_models(store,models):
    """Atomic cache update, not insertion into the user's personal vehicle list."""
    ensure_schema(store)
    timestamp=dt.datetime.now(dt.timezone.utc).isoformat()
    for m in models:
        if not isinstance(m,dict) or not all(k in m for k in
            ("make_id","model_id","make_name","model_name","model_year")):
            raise ValueError("Incomplete verified model")
        if not (isinstance(m["make_id"],int) and isinstance(m["model_id"],int)
                and isinstance(m["model_year"],int)
                and isinstance(m["make_name"],str) and isinstance(m["model_name"],str)
                and 0<len(m["make_name"])<=80 and 0<len(m["model_name"])<=120):
            raise ValueError("Invalid model")
    try:
        store.db.execute("BEGIN IMMEDIATE")
        for m in models:
            store.db.execute("""INSERT INTO public_vehicle_models
             (make_id,model_id,make_name,model_name,model_year,source,retrieved_utc)
             VALUES(?,?,?,?,?,?,?)
             ON CONFLICT(make_id,model_id,model_year) DO UPDATE SET
             make_name=excluded.make_name,model_name=excluded.model_name,
             source=excluded.source,retrieved_utc=excluded.retrieved_utc""",
             (m["make_id"],m["model_id"],m["make_name"],m["model_name"],
              m["model_year"],SOURCE,timestamp))
        store.db.commit()
    except BaseException:
        store.db.rollback()
        raise
    return len(models)

def cached_models(store,make,year):
    make,year=valid_query(make,year)
    ensure_schema(store)
    return store.db.execute("""SELECT make_id,model_id,make_name,model_name,model_year,
      source,retrieved_utc FROM public_vehicle_models WHERE make_name=? COLLATE NOCASE
      AND model_year=? ORDER BY model_name COLLATE NOCASE""",(make,year)).fetchall()
