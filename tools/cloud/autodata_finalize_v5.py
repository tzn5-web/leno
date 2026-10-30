# Autodata cloud: reparație ZIP + încărcare Drive în sesiunea Colab EXISTENTĂ
# Rulează exclusiv după verificarea și extragerea completă: RAR_EXTRACT=PASS.
REQUIRED=("ROOT","ARCHIVE","EXTRACT","PACKS","EXPECTED","sha","PACK_LIMIT","service","OUTPUT_FOLDER_NAME","MediaFileUpload")
missing=[name for name in REQUIRED if name not in globals()]
if missing:
    raise RuntimeError("Variabile Colab lipsă: "+", ".join(missing)+". Folosește runtime-ul în care s-a extras RAR-ul.")

# V5 — pachetizare corectată și verificată pentru fișiere inclusiv de >64 MiB.
# Nu descarcă sau extrage din nou arhiva. Se poate executa direct după RAR_EXTRACT=PASS.
import zipfile
import hashlib

SEGMENT_BYTES = 64 * 1024 * 1024
ZIP_LIMIT = PACK_LIMIT                  # 180 MiB
ENTRY_RESERVE = 4096                    # overhead conservator pentru antete ZIP / nume de fișiere

def segment_lengths(file_size, segment_size):
    if file_size < 0 or segment_size <= 0:
        raise ValueError("Dimensiuni invalide.")
    remaining = file_size
    while remaining > 0:
        n = min(segment_size, remaining)
        yield n
        remaining -= n

# Regresie pentru eroarea ValueError: read length must be non-negative or -1.
assert list(segment_lengths(0, 64)) == []
assert list(segment_lengths(1, 64)) == [1]
assert list(segment_lengths(64, 64)) == [64]
assert list(segment_lengths(65, 64)) == [64, 1]
assert list(segment_lengths(129, 64)) == [64, 64, 1]
print("SPLIT_UNIT_TEST=PASS")

if not EXTRACT.is_dir():
    raise RuntimeError("Folderul extras nu există în această sesiune Colab. Verifică RAR_EXTRACT=PASS.")
entries = []
for p in sorted(EXTRACT.rglob("*")):
    if p.is_file() and not p.is_symlink():
        entries.append((p, p.relative_to(EXTRACT).as_posix(), p.stat().st_size))
if not entries:
    raise RuntimeError("Nu s-au găsit fișiere extrase.")
if len(entries) > 150000:
    raise RuntimeError("Prea multe fișiere pentru pachetizare automată.")
total_bytes = sum(size for _, _, size in entries)
print("Fișiere extrase:", len(entries), "Volum:", round(total_bytes / 2**30, 2), "GiB")
PACKS.mkdir(parents=True, exist_ok=True)
# Șterge doar ZIP-urile temporare incomplete din încercarea anterioară,
# niciodată arhiva RAR sau directorul EXTRACT.
for old in PACKS.glob("autodata_part_*.zip"):
    old.unlink()
if shutil.disk_usage("/content").free < total_bytes + 128*1024**2:
    raise RuntimeError(
        "Spațiu Colab insuficient pentru ZIP-urile temporare. "
        "RAR-ul și fișierele deja extrase sunt păstrate.")

packing = []
part_number = 0
used = 0
z = None
packname = None

def next_pack():
    global part_number, used, z, packname
    if z is not None:
        z.close()
    part_number += 1
    used = 0
    packname = f"autodata_part_{part_number:04d}.zip"
    z = zipfile.ZipFile(PACKS / packname, "w", compression=zipfile.ZIP_STORED, allowZip64=True)
    print("Construiesc:", packname)

try:
    next_pack()
    for source, relative, size in entries:
        chunks = []
        if size == 0:
            if used + ENTRY_RESERVE > ZIP_LIMIT:
                next_pack()
            z.writestr(relative, b"")
            used += ENTRY_RESERVE
            chunks.append({"package": packname, "entry": relative, "bytes": 0,
                           "sha256": hashlib.sha256(b"").hexdigest()})
        else:
            with source.open("rb") as src:
                copied = 0
                for index, read_size in enumerate(segment_lengths(size, SEGMENT_BYTES)):
                    data = src.read(read_size)
                    if len(data) != read_size:
                        raise IOError(f"Citire incompletă: {relative} la offset {copied}, {len(data)}/{read_size}")
                    entry = (relative if size <= SEGMENT_BYTES
                             else f"{relative}.chunk{index:04d}")
                    if used + len(data) + ENTRY_RESERVE > ZIP_LIMIT:
                        next_pack()
                    z.writestr(entry, data)
                    used += len(data) + ENTRY_RESERVE
                    copied += len(data)
                    chunks.append({"package": packname, "entry": entry, "bytes": len(data),
                                   "sha256": hashlib.sha256(data).hexdigest()})
                if copied != size or src.read(1):
                    raise RuntimeError(f"Fișier modificat în timpul pachetizării: {relative}")
        packing.append({"path": relative, "size_bytes": size, "chunks": chunks})
finally:
    if z is not None:
        z.close()

packages = sorted(PACKS.glob("autodata_part_*.zip"))
for package in packages:
    if package.stat().st_size >= 190 * 1024 * 1024:
        raise RuntimeError(f"ZIP prea mare pentru conector: {package.name}")
    with zipfile.ZipFile(package) as zp:
        problem = zp.testzip()
        if problem:
            raise RuntimeError(f"ZIP corupt: {package.name} / {problem}")
print("ZIP_TEST=PASS")

manifest = {
    "archive": ARCHIVE.name,
    "original_bytes": EXPECTED,
    "sha256": sha.hexdigest(),
    "file_count": len(packing),
    "total_extracted_bytes": total_bytes,
    "package_count": len(packages),
    "files": packing,
}
(ROOT / "INVENTAR.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
(ROOT / "INVENTAR.txt").write_text(
    "\n".join(f"{x['size_bytes']:>14} {x['path']}" for x in packing),
    encoding="utf-8")
print("PACKAGING=PASS FILES=", len(entries), "PACKAGES=", len(packages))

# Upload direct prin Drive API, fără drive.mount(), cu retry și posibilitate de reluare la rerulare.
from googleapiclient.errors import HttpError
def api_call(request):
    for attempt in range(8):
        try: return request.execute(num_retries=4)
        except HttpError as e:
            status=e.resp.status
            if status not in (429,500,502,503,504) and not (status==403 and b"rateLimitExceeded" in e.content):
                raise
            time.sleep(min(3*2**attempt,60))
    raise RuntimeError("Google Drive API: prea multe erori la operație.")
def drive_query(q):
    return api_call(service.files().list(q=q,fields="nextPageToken,files(id,name,size,mimeType)",pageSize=100,spaces="drive")).get("files",[])
matches=drive_query("name = '"+OUTPUT_FOLDER_NAME+"' and mimeType = 'application/vnd.google-apps.folder' and trashed = false")
folder_id = matches[0]["id"] if matches else api_call(service.files().create(
    body={"name":OUTPUT_FOLDER_NAME,"mimeType":"application/vnd.google-apps.folder"},
    fields="id")).get("id")
print("Folder destinație:",f"https://drive.google.com/drive/folders/{folder_id}")
def upload_one(localfile):
    # Evită duplicatele și reîncărcarea fișierelor deja finalizate în Drive.
    fname=localfile.name.replace("'","\\'")
    existing=drive_query(f"name = '{fname}' and '{folder_id}' in parents and trashed = false")
    for item in existing:
        if int(item.get("size","-1"))==localfile.stat().st_size:
            print("Există deja:",localfile.name)
            return item["id"]
    media=MediaFileUpload(str(localfile),mimetype="application/zip" if localfile.suffix==".zip" else "application/octet-stream",
                          chunksize=8*1024*1024,resumable=True)
    task=service.files().create(body={"name":localfile.name,"parents":[folder_id]},media_body=media,fields="id,name,size")
    result=None
    while result is None:
        progress,result=task.next_chunk(num_retries=7)
    print("UPLOAD OK:",localfile.name)
    return result["id"]
for source in [ROOT/"INVENTAR.json", ROOT/"INVENTAR.txt",ROOT/"listare_7z.txt"]+packages:
    upload_one(source)
# Marcare succes după ce toate pachetele au fost încărcate.
done=ROOT/"TRANSFER_FINALIZAT.txt"
done.write_text(f"PASS\nArchive SHA256: {sha.hexdigest()}\nPachete: {len(packages)}\nFișiere: {len(entries)}\n")
upload_one(done)
print("\nTRANSFER FINALIZAT. Verifică în Google Drive folderul Autodata_3_45_EXTRACTED")
print(f"https://drive.google.com/drive/folders/{folder_id}")
