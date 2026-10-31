"""Regression: the base ZIP reader must never touch blocked part 0016."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from original_archive_preflight import audit

BLOCKED = "autodata_part_0016.zip"

class BlockedArchiveReaderTests(unittest.TestCase):
    def test_blocked_archive_is_not_opened_even_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = "Autodata__3.45/INSTALLATION INSTRUCTIONS.txt"
            data = b"SYNTHETIC-NO-REAL-ARCHIVE"
            manifest = {"files": [{
                "path": name, "size_bytes": len(data), "chunks": [{
                    "package": BLOCKED, "entry": name,
                    "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()
                }]
            }], "package_count": 1}
            path = root / "INVENTAR.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            (root / BLOCKED).write_bytes(b"INTENTIONALLY NOT A ZIP")
            with patch("original_archive_preflight.zipfile.ZipFile", side_effect=AssertionError("BLOCKED PACKAGE WAS OPENED")):
                report = audit(path, root)
            self.assertEqual(report["missing_packages"], [BLOCKED])
            self.assertEqual(report["verified_chunk_count"], 0)
            self.assertFalse(report["complete_archive"])
            self.assertFalse(report["license_verified"])

if __name__ == "__main__":
    unittest.main()
