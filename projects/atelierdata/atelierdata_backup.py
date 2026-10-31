"""Complete, verified ZIP backups for user-owned AtelierData databases and documents."""
from __future__ import annotations
import hashlib, json, os, shutil, sqlite3, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path
from atelierdata_extensions import _SAFE_NAME, resolve_document

MAX_DOCUMENT = 128 * 1024 * 1024
MAX_DATABASE = 256 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def backup_bundle(store, destination):
    """Create a consistent SQLite snapshot plus SHA256-checked managed documents."""
    destination = Path(destination)
    if destination.suffix.lower() != '.zip' or destination.resolve() == store.path.resolve():
        raise ValueError('Backup-ul trebuie salvat ca ZIP, nu peste baza SQLite')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / 'database.sqlite3'
        conn = sqlite3.connect(snapshot)
        try:
            store.db.backup(conn)
        finally:
            conn.close()
        if snapshot.stat().st_size > MAX_DATABASE:
            raise ValueError('Baza depășește limita de 256 MiB')
        verify = sqlite3.connect(snapshot)
        try:
            if verify.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Snapshot SQLite invalid')
            if verify.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Relații SQLite invalide')
            attachments = verify.execute('SELECT id,path FROM attachments ORDER BY id').fetchall()
        finally:
            verify.close()
        documents = {}
        total = snapshot.stat().st_size
        for attachment_id, name in attachments:
            if not _SAFE_NAME.fullmatch(name):
                raise ValueError('Atașament vechi fără cale administrată: ' + name)
            path = resolve_document(store, attachment_id)
            if path.stat().st_size > (MAX_DOCUMENT if path.suffix.lower()=='.pdf' else 32*1024*1024):
                raise ValueError('Atașament prea mare')
            total += path.stat().st_size
            if total > MAX_TOTAL:
                raise ValueError('Backup depășește 2 GiB')
            documents[name] = path
        fd, temp_zip = tempfile.mkstemp(prefix='.atelierdata-backup-', suffix='.zip',
                                        dir=str(destination.parent))
        os.close(fd)
        try:
            hashes = {}
            with zipfile.ZipFile(temp_zip, 'w', compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=6) as archive:
                archive.write(snapshot, 'database.sqlite3')
                for name, path in sorted(documents.items()):
                    archive.write(path, 'documents/' + name)
                    hashes[name] = _sha(path)
                manifest = {
                    'format': 'atelierdata-backup-v1',
                    'created_utc': datetime.now(timezone.utc).isoformat(),
                    'database_sha256': _sha(snapshot),
                    'documents': hashes,
                    'original_proprietary_data_automatically_included': False
                }
                archive.writestr('manifest.json', json.dumps(manifest, indent=2))
            os.replace(temp_zip, destination)
        finally:
            if os.path.exists(temp_zip):
                os.unlink(temp_zip)
    return {'documents': len(documents), 'bytes': destination.stat().st_size}


def restore_bundle(archive_path, new_directory):
    """Restore only into a new directory, after validating every member and SQLite."""
    archive_path = Path(archive_path)
    destination = Path(new_directory)
    if destination.exists():
        raise FileExistsError('Destinația trebuie să fie un director nou, inexistent')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        if 'manifest.json' not in names or 'database.sqlite3' not in names:
            raise ValueError('Backup incomplet')
        if archive.getinfo('manifest.json').file_size > 1024 * 1024:
            raise ValueError('Manifest prea mare')
        manifest = json.loads(archive.read('manifest.json'))
        if not isinstance(manifest, dict):
            raise ValueError('Manifest invalid')
        if manifest.get('format') != 'atelierdata-backup-v1':
            raise ValueError('Versiune backup necunoscută')
        docs = manifest.get('documents')
        if not isinstance(docs, dict):
            raise ValueError('Manifest invalid')
        expected = {'manifest.json', 'database.sqlite3'}
        for name in docs:
            if not _SAFE_NAME.fullmatch(name):
                raise ValueError('Nume fișier invalid')
            expected.add('documents/' + name)
        if names != expected or len(archive.namelist()) != len(expected):
            raise ValueError('Fișiere neașteptate sau duplicate în ZIP')
        total = 0
        for info in archive.infolist():
            limit = MAX_DATABASE if info.filename == 'database.sqlite3' else (MAX_DOCUMENT if info.filename.lower().endswith('.pdf') else 32*1024*1024)
            if info.filename == 'manifest.json':
                limit = 1024 * 1024
            if info.file_size > limit:
                raise ValueError('Fișier depășește limita permisă')
            total += info.file_size
        if total > MAX_TOTAL:
            raise ValueError('Arhiva depășește 2 GiB decomprimat')
        with tempfile.TemporaryDirectory(prefix='.atelierdata-restore-',
                                          dir=str(destination.parent)) as temp:
            staging = Path(temp)
            (staging / 'documents').mkdir()
            for name in sorted(expected - {'manifest.json'}):
                target = staging / name
                with archive.open(name) as inp, target.open('wb') as out:
                    shutil.copyfileobj(inp, out, 1024 * 1024)
                expected_sha = (manifest['database_sha256'] if name == 'database.sqlite3'
                                else docs[name.split('/', 1)[1]])
                if _sha(target) != expected_sha:
                    raise ValueError('SHA256 invalid: ' + name)
            database = staging / 'database.sqlite3'
            conn = sqlite3.connect('file:' + database.as_posix() + '?mode=ro', uri=True)
            try:
                if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise ValueError('Baza SQLite restaurată este invalidă')
                if conn.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('Relații SQLite invalide')
                used = {row[0] for row in conn.execute('SELECT path FROM attachments')}
                if used != set(docs):
                    raise ValueError('Manifestul nu corespunde atașamentelor din bază')
            finally:
                conn.close()
            os.replace(staging, destination)
    return destination / 'database.sqlite3'
