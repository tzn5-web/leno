"""Synthetic user-owned backup verification tests; no original binaries or IDF."""
import hashlib
import json
import os
import subprocess
import sys
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from backup_verification import verify_backup_bundle


class BackupVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "source.sqlite3"
        conn = sqlite3.connect(self.database)
        try:
            conn.executescript("""CREATE TABLE attachments(id INTEGER PRIMARY KEY, path TEXT NOT NULL);
                CREATE TABLE articles(id INTEGER PRIMARY KEY, title TEXT NOT NULL);
                CREATE TABLE vehicles(id INTEGER PRIMARY KEY, make TEXT NOT NULL);
            """)
            conn.commit()
        finally:
            conn.close()
        self.document = b"%PDF-1.4\nsynthetic user-owned document\n%%EOF"
        self.doc_hash = hashlib.sha256(self.document).hexdigest()
        self.doc_name = self.doc_hash + ".pdf"
        conn = sqlite3.connect(self.database)
        try:
            conn.execute("INSERT INTO attachments(path) VALUES(?)", (self.doc_name,))
            conn.commit()
        finally:
            conn.close()
        self.db_bytes = self.database.read_bytes()
        self.manifest = {"format": "atelierdata-backup-v1",
                         "database_sha256": hashlib.sha256(self.db_bytes).hexdigest(),
                         "documents": {self.doc_name: self.doc_hash}}
        self.members = {"manifest.json": json.dumps(self.manifest).encode(),
                        "database.sqlite3": self.db_bytes,
                        "documents/" + self.doc_name: self.document}

    def _zip(self, name="backup.zip", members=None):
        destination = self.root / name
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, contents in (members or self.members).items():
                archive.writestr(path, contents)
        return destination

    def test_valid_backup_is_verified_without_restoring(self):
        result = verify_backup_bundle(self._zip())
        self.assertTrue(result["verified"])
        self.assertEqual(result["documents"], 1)
        self.assertEqual(result["attachment_references"], 1)
        self.assertFalse(result["original_proprietary_data_decoded"])
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),
                         ["backup.zip", "source.sqlite3"])

    def test_corrupt_document_rejected(self):
        members = dict(self.members)
        members["documents/" + self.doc_name] = b"tampered"
        with self.assertRaisesRegex(ValueError, "Document SHA256"):
            verify_backup_bundle(self._zip(members=members))

    def test_corrupt_database_rejected(self):
        members = dict(self.members)
        members["database.sqlite3"] = b"corrupt"
        with self.assertRaisesRegex(ValueError, "Database SHA256"):
            verify_backup_bundle(self._zip(members=members))

    def test_traversal_member_rejected(self):
        members = dict(self.members)
        members["../outside.txt"] = b"evil"
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            verify_backup_bundle(self._zip(members=members))

    def test_malformed_manifest_rejected(self):
        members = dict(self.members)
        members["manifest.json"] = b"[]"
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            verify_backup_bundle(self._zip(members=members))

    def test_wrong_document_digest_rejected(self):
        manifest = dict(self.manifest)
        manifest["documents"] = {self.doc_name: "0" * 64}
        members = dict(self.members)
        members["manifest.json"] = json.dumps(manifest).encode()
        with self.assertRaisesRegex(ValueError, "disagreement"):
            verify_backup_bundle(self._zip(members=members))

    def test_duplicate_members_rejected(self):
        target = self.root / "duplicate.zip"
        with zipfile.ZipFile(target, "w") as archive:
            for name, data in self.members.items():
                archive.writestr(name, data)
            archive.writestr("manifest.json", self.members["manifest.json"])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            verify_backup_bundle(target)

    def test_database_reference_mismatch_rejected(self):
        conn = sqlite3.connect(self.database)
        try:
            conn.execute("DELETE FROM attachments")
            conn.commit()
        finally:
            conn.close()
        contents = self.database.read_bytes()
        manifest = dict(self.manifest)
        manifest["database_sha256"] = hashlib.sha256(contents).hexdigest()
        members = dict(self.members)
        members["database.sqlite3"] = contents
        members["manifest.json"] = json.dumps(manifest).encode()
        with self.assertRaisesRegex(ValueError, "attachments differ"):
            verify_backup_bundle(self._zip(members=members))

    def test_cli_verifies_without_creating_default_database(self):
        archive = self._zip()
        isolated_home = self.root / "isolated-localappdata"
        env = os.environ.copy()
        env["LOCALAPPDATA"] = str(isolated_home)
        command = [sys.executable, str(Path(__file__).with_name("atelierdata.py")),
                   "--verify-backup", str(archive)]
        result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VERIFY_BACKUP=PASS", result.stdout)
        self.assertFalse(isolated_home.exists())

    def test_symlink_zip_rejected_when_supported(self):
        target = self._zip()
        link = self.root / "link.zip"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink unsupported")
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            verify_backup_bundle(link)


if __name__ == "__main__":
    unittest.main()
