"""Read-only verification of user-created AtelierData ZIP backups.

Validates manifest, every ZIP member's SHA256, SQLite integrity and attachment
referential consistency without restoring into the user's live database.
No original Autodata/IDF files are read or interpreted.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import stat
import tempfile
import zipfile
from pathlib import Path

from atelierdata_backup import MAX_DATABASE, MAX_DOCUMENT, MAX_TOTAL
from atelierdata_extensions import _SAFE_NAME

MAX_MANIFEST = 1024 * 1024
MAX_ENTRIES = 10000
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _digest(stream, output=None, limit=MAX_DOCUMENT):
    sha = hashlib.sha256()
    total = 0
    while True:
        block = stream.read(1024 * 1024)
        if not block:
            break
        total += len(block)
        if total > limit:
            raise ValueError("ZIP member exceeds permitted size")
        sha.update(block)
        if output is not None:
            output.write(block)
    return sha.hexdigest(), total


def verify_backup_bundle(archive_path):
    """Return non-sensitive aggregate verification metadata or raise ValueError.

    The SQLite snapshot is inspected in an isolated temporary directory and
    deleted afterwards. No files are extracted to the requested restore path.
    """
    path = Path(archive_path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Backup missing or symbolic link")
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) < 2 or len(members) > MAX_ENTRIES:
                raise ValueError("Unexpected ZIP member count")
            names = [member.filename for member in members]
            if len(set(names)) != len(names):
                raise ValueError("Duplicate ZIP members")
            info_by_name = {item.filename: item for item in members}
            if "manifest.json" not in info_by_name or "database.sqlite3" not in info_by_name:
                raise ValueError("Backup manifest or database missing")
            total_size = 0
            for member in members:
                if member.flag_bits & 1:
                    raise ValueError("Encrypted ZIP members unsupported")
                mode = (member.external_attr >> 16) & 0xffff
                if stat.S_IFMT(mode) == stat.S_IFLNK:
                    raise ValueError("ZIP symlink forbidden")
                if member.is_dir():
                    raise ValueError("ZIP directories forbidden")
                limit = (MAX_MANIFEST if member.filename == "manifest.json" else
                         MAX_DATABASE if member.filename == "database.sqlite3" else
                         MAX_DOCUMENT if member.filename.lower().endswith(".pdf") else 32 * 1024 * 1024)
                if member.file_size > limit:
                    raise ValueError("ZIP member too large")
                total_size += member.file_size
                if total_size > MAX_TOTAL:
                    raise ValueError("ZIP uncompressed size limit exceeded")
            with archive.open("manifest.json") as source:
                raw = source.read(MAX_MANIFEST + 1)
            if len(raw) > MAX_MANIFEST:
                raise ValueError("Manifest too large")
            manifest = json.loads(raw.decode("utf-8"))
            if not isinstance(manifest, dict) or manifest.get("format") != "atelierdata-backup-v1":
                raise ValueError("Unsupported backup manifest")
            docs = manifest.get("documents")
            if not isinstance(docs, dict) or len(docs) > MAX_ENTRIES - 2:
                raise ValueError("Invalid documents manifest")
            db_sha = manifest.get("database_sha256")
            if not isinstance(db_sha, str) or not _SHA256.fullmatch(db_sha):
                raise ValueError("Invalid database digest")
            for name, digest in docs.items():
                if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name):
                    raise ValueError("Invalid document name")
                if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                    raise ValueError("Invalid document digest")
                if digest != name[:64]:
                    raise ValueError("Document name/digest disagreement")
            expected = {"manifest.json", "database.sqlite3"} | {"documents/" + n for n in docs}
            if set(names) != expected:
                raise ValueError("Unexpected or missing ZIP members")
            with tempfile.TemporaryDirectory(prefix="atelierdata-verify-") as temp:
                snapshot = Path(temp) / "database.sqlite3"
                with archive.open("database.sqlite3") as source, snapshot.open("wb") as out:
                    actual, count = _digest(source, out, MAX_DATABASE)
                if actual != db_sha or count != info_by_name["database.sqlite3"].file_size:
                    raise ValueError("Database SHA256/size mismatch")
                for name, expected_sha in docs.items():
                    member_name = "documents/" + name
                    with archive.open(member_name) as source:
                        actual, count = _digest(source, limit=MAX_DOCUMENT if name.endswith(".pdf") else 32 * 1024 * 1024)
                    if actual != expected_sha or count != info_by_name[member_name].file_size:
                        raise ValueError("Document SHA256/size mismatch")
                conn = sqlite3.connect("file:" + snapshot.as_posix() + "?mode=ro", uri=True)
                try:
                    conn.execute("PRAGMA query_only=ON")
                    conn.execute("PRAGMA trusted_schema=OFF")
                    if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise ValueError("SQLite integrity check failed")
                    if conn.execute("PRAGMA foreign_key_check").fetchall():
                        raise ValueError("SQLite foreign key check failed")
                    rows = conn.execute("SELECT path FROM attachments").fetchall()
                    if any(not isinstance(row[0], str) for row in rows):
                        raise ValueError("Invalid SQLite attachment path")
                    if {row[0] for row in rows} != set(docs):
                        raise ValueError("SQLite attachments differ from manifest")
                except sqlite3.DatabaseError as exc:
                    raise ValueError("Invalid SQLite snapshot") from exc
                finally:
                    conn.close()
            return {"schema": "atelierdata-backup-verification-v1", "verified": True,
                    "documents": len(docs), "attachment_references": len(rows),
                    "uncompressed_bytes": total_size, "database_sha256": db_sha,
                    "original_proprietary_data_decoded": False}
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or damaged backup ZIP") from exc
