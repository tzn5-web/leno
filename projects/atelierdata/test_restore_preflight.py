"""Restore security regressions using synthetic, user-created AtelierData data only."""
from __future__ import annotations

import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from atelierdata import Store
from atelierdata_backup import backup_bundle, restore_bundle
from atelierdata_extensions import attach_document


class RestorePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "catalog.sqlite3")
        self.addCleanup(self.store.close)
        vid = self.store.add_vehicle("Synthetic", "Test")
        aid = self.store.add_article(vid, "Note atelier", "Authorized fixture")
        pdf = self.root / "authorized.pdf"
        pdf.write_bytes(b"%PDF-1.4\nSynthetic user-owned data\n%%EOF\n")
        attach_document(self.store, aid, pdf)
        self.backup = self.root / "backup.zip"
        backup_bundle(self.store, self.backup)

    def _rewrite(self, filename, transform):
        with zipfile.ZipFile(self.backup) as original:
            payload = [(item.filename, original.read(item)) for item in original.infolist()]
        target = self.root / filename
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as out:
            for name, data in payload:
                info, replacement = transform(name, data)
                out.writestr(info if info is not None else name, replacement)
        return target

    def test_verified_backup_restores_into_new_directory(self):
        restored = self.root / "restored"
        database = restore_bundle(self.backup, restored)
        self.assertEqual(database, restored / "database.sqlite3")
        self.assertTrue(database.is_file())
        self.assertEqual(len(list((restored / "documents").iterdir())), 1)

    def test_zip_symlink_member_is_rejected_before_restore(self):
        def transform(name, data):
            if not name.startswith("documents/"):
                return None, data
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            return info, data

        tampered = self._rewrite("symlink.zip", transform)
        destination = self.root / "blocked-symlink"
        with self.assertRaisesRegex(ValueError, "symlink"):
            restore_bundle(tampered, destination)
        self.assertFalse(destination.exists())

    def test_invalid_manifest_digest_is_rejected_before_restore(self):
        def transform(name, data):
            if name != "manifest.json":
                return None, data
            obj = json.loads(data)
            obj["database_sha256"] = "not-a-sha256"
            return None, json.dumps(obj).encode("utf-8")

        tampered = self._rewrite("bad-manifest.zip", transform)
        destination = self.root / "blocked-manifest"
        with self.assertRaisesRegex(ValueError, "digest"):
            restore_bundle(tampered, destination)
        self.assertFalse(destination.exists())

    def test_symlink_source_archive_is_rejected_when_supported(self):
        link = self.root / "backup-link.zip"
        try:
            link.symlink_to(self.backup)
        except (OSError, NotImplementedError):
            self.skipTest("Symbolic links unavailable")
        destination = self.root / "blocked-link"
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            restore_bundle(link, destination)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
