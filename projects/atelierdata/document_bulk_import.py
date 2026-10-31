"""Explicit batch import from a locally selected folder into AtelierData.

For user-controlled documents only. No crawling of websites, archive extraction,
automatic rights inference, or guessed vehicle mapping. Duplicates within the
same exact vehicle are skipped by digest; all failures are reported.
"""
import hashlib
from pathlib import Path
from document_library import import_local_file,ACCESS_RIGHTS,DOCUMENT_TYPES

EXTENSIONS={".pdf",".png",".jpg",".jpeg",".txt"}
MAX_FILES=500
MAX_INPUT_SIZE=32*1024*1024

def _sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def _check_signature(path):
    suffix=path.suffix.lower()
    with path.open("rb") as f:
        first=f.read(4096)
    if suffix==".pdf" and not first.lstrip().startswith(b"%PDF-"):
        raise ValueError("Semnătură PDF invalidă")
    if suffix==".png" and not first.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Semnătură PNG invalidă")
    if suffix in (".jpg",".jpeg") and not first.startswith(b"\xff\xd8\xff"):
        raise ValueError("Semnătură JPEG invalidă")
    if suffix==".txt":
        if b"\x00" in first or first.startswith((b"MZ",b"PK\x03\x04")):
            raise ValueError("Fișier TXT nu pare text")

def bulk_import_folder(store,vehicle_id,folder,source_name,rights_basis,category="Alt document",
                       language="",market="",include_subfolders=True):
    if rights_basis not in ACCESS_RIGHTS or rights_basis=="neconfirmat":
        raise ValueError("Confirmarea drepturilor asupra materialelor este obligatorie")
    if category not in DOCUMENT_TYPES:raise ValueError("Categorie invalidă")
    if not isinstance(source_name,str) or not source_name.strip():
        raise ValueError("Sursa este obligatorie")
    if store.db.execute("SELECT id FROM vehicles WHERE id=?",(vehicle_id,)).fetchone() is None:
        raise ValueError("Selectează o motorizare validă")
    root=Path(folder).expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError("Director invalid")
    paths=sorted(root.rglob("*") if include_subfolders else root.iterdir())
    allowed=[f for f in paths if f.suffix.lower() in EXTENSIONS]
    if len(allowed)>MAX_FILES:
        raise ValueError("Prea multe fișiere; limitează selecția la 500")
    present={
        row[0] for row in store.db.execute("""SELECT att.path FROM attachments att
            JOIN articles art ON art.id=att.article_id WHERE art.vehicle_id=?""",
            (vehicle_id,))
    }
    report={"scanned":len(allowed),"imported":0,"duplicates":0,
            "failed":[],"files_without_supported_extension":len(paths)-len(allowed),
            "vehicle_id":vehicle_id}
    for path in allowed:
        try:
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                raise ValueError("Fișier nepermis sau legătură simbolică")
            size=path.stat().st_size
            if not 0<size<=MAX_INPUT_SIZE:
                raise ValueError("Fișier gol sau mai mare de 32 MiB")
            _check_signature(path)
            key=_sha(path)+path.suffix.lower()
            if key in present:
                report["duplicates"]+=1
                continue
            import_local_file(
                store,vehicle_id,path,category=category,title=path.stem[:260],
                source_name=source_name,rights_basis=rights_basis,
                language=language,market=market,
                applicability_note="Document din folder local. Modelul/motorul exact trebuie verificat.")
            report["imported"]+=1
            present.add(key)
        except (OSError,ValueError) as exc:
            report["failed"].append({"file":str(path.relative_to(root)),"reason":str(exc)[:220]})
    return report
