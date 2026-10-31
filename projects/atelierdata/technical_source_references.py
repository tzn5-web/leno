"""Save a provider reference to a vehicle without copying provider content.

This creates a clearly marked external-source pointer inside the existing
articles table. It is NOT an imported workshop manual or automotive fact.
"""
from __future__ import annotations
from technical_sources import SOURCES, ALL, normalize

def get_source(key):
    return next((source for source in SOURCES if source.key==key),None)

def save_source_reference(store,vehicle_id,source_key):
    source=get_source(source_key)
    if source is None:raise ValueError("Sursă necunoscută")
    row=store.db.execute(
        "SELECT make,model,engine,years FROM vehicles WHERE id=?",(vehicle_id,)).fetchone()
    if row is None:raise ValueError("Vehicul inexistent")
    aliases={"vauxhall":"opel","škoda":"skoda","vw":"volkswagen",
             "mini cooper":"mini","citroën":"citroen"}
    make=aliases.get(normalize(row["make"]),normalize(row["make"]))
    if ALL not in source.makes and make not in {normalize(m) for m in source.makes}:
        raise ValueError("Sursa nu este inclusă pentru marca selectată")
    category="Note atelier"
    title="[Referință online] "+source.title
    # Preserve provider URL and do not fabricate vehicle-specific service content.
    notes=("Referință externă — nu conține date tehnice importate.\n"
           f"URL: {source.url}\n"
           f"Acces: {source.access}\n"
           f"Piață: {source.market}\n"
           f"Tipuri: {', '.join(source.categories)}\n"
           f"Precizări: {source.notes}\n"
           "Alege modelul, motorizarea, anul și documentul exact pe site. "
           "Nu copia conținutul fără drepturi de reutilizare.")
    old=store.db.execute(
        "SELECT id FROM articles WHERE vehicle_id=? AND category=? "
        "AND title=? AND source=? ORDER BY id LIMIT 1",
        (vehicle_id,category,title,source.url)).fetchone()
    if old:return {"article_id":old["id"],"created":False}
    article_id=store.add_article(vehicle_id,category,title,notes,source.url)
    return {"article_id":article_id,"created":True}
