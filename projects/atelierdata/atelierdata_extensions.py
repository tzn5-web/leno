"""AtelierData user-owned document storage, integrity and export.
No proprietary IDF parsing, binary execution, or automatic content acquisition.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

_ALLOWED = {'.pdf', '.png', '.jpg', '.jpeg', '.txt'}
_MAX_SIZE = 32 * 1024 * 1024
_SAFE_NAME = re.compile(r'^[0-9a-f]{64}\.(?:pdf|png|jpe?g|txt)$')


def integrity_check(store):
    sqlite_errors = [row[0] for row in store.db.execute('PRAGMA quick_check') if row[0] != 'ok']
    fk_errors = [tuple(row) for row in store.db.execute('PRAGMA foreign_key_check')]
    return {'ok': not sqlite_errors and not fk_errors,
            'sqlite_errors': sqlite_errors, 'foreign_key_errors': fk_errors}


def export_records(store, destination):
    """Atomically export only manually entered vehicle/article data."""
    destination = Path(destination)
    if destination.resolve() == store.path.resolve():
        raise ValueError('Nu suprascrie baza SQLite')
    destination.parent.mkdir(parents=True, exist_ok=True)
    query = ('SELECT v.make,v.model,v.engine,v.years,v.fuel,v.variant,'
             'a.category,a.title,a.content,a.source FROM articles a '
             'JOIN vehicles v ON v.id=a.vehicle_id '
             'ORDER BY v.make,v.model,a.category,a.title')
    records = [dict(row) for row in store.db.execute(query)]
    payload = {'schema': 'atelierdata-records-v1', 'records': records}
    fd, temporary = tempfile.mkstemp(prefix='.atelierdata-', dir=str(destination.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as out:
            json.dump(payload, out, ensure_ascii=False, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(records)


def attach_document(store, article_id, source):
    """Copy an explicitly selected user-owned document into managed storage."""
    source = Path(source)
    if source.is_symlink() or not source.is_file() or source.suffix.lower() not in _ALLOWED:
        raise ValueError('Accept numai PDF, PNG, JPG, JPEG și TXT')
    if store.get_article(article_id) is None:
        raise ValueError('Documentul nu există')
    if source.stat().st_size > _MAX_SIZE:
        raise ValueError('Fișierul depășește 32 MiB')
    folder = store.path.parent / 'documents'
    folder.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=str(folder))
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(fd, 'wb') as out, source.open('rb') as inp:
            while True:
                block = inp.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > _MAX_SIZE:
                    raise ValueError('Fișierul depășește 32 MiB')
                digest.update(block)
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        stored_name = digest.hexdigest() + source.suffix.lower()
        dest = folder / stored_name
        if dest.exists():
            os.unlink(temporary)
        else:
            os.replace(temporary, dest)
        found = store.db.execute(
            'SELECT id FROM attachments WHERE article_id=? AND path=?',
            (article_id, stored_name)).fetchone()
        if found:
            return found[0]
        cursor = store.db.execute(
            'INSERT INTO attachments(article_id,path) VALUES(?,?)',
            (article_id, stored_name))
        store.db.commit()
        return cursor.lastrowid
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def list_documents(store, article_id):
    return store.db.execute(
        'SELECT * FROM attachments WHERE article_id=? ORDER BY id',
        (article_id,)).fetchall()


def resolve_document(store, attachment_id):
    """Verify managed path and SHA256 before returning it to the OS document viewer."""
    row = store.db.execute(
        'SELECT * FROM attachments WHERE id=?', (attachment_id,)).fetchone()
    if row is None:
        raise FileNotFoundError('Atașament inexistent')
    name = row['path']
    if not _SAFE_NAME.fullmatch(name):
        raise ValueError('Cale invalidă')
    target = store.path.parent / 'documents' / name
    if target.is_symlink() or not target.is_file():
        raise FileNotFoundError('Fișier lipsă')
    digest = hashlib.sha256()
    with target.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != name[:64]:
        raise ValueError('Atașament modificat sau corupt')
    return target
