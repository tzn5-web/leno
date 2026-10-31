"""Synthetic-only tests for evidence-ledger crosschecking."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from original_evidence_ledger_crosscheck import crosscheck
from original_archive_preflight import BLOCKED_PACKAGE

FIELDS = ("path", "expected_size", "actual_size", "sha256_reconstructed",
          "chunk_count", "status", "problems", "category")
DOWNLOAD_FIELDS = ("name", "bytes", "sha256", "status")


def sha(data):
    return hashlib.sha256(data).hexdigest()


class EvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest_path = self.root / "INVENTAR.json"
        self.reconstructed_path = self.root / "manifest_vs_actual.csv"
        self.downloads_path = self.root / "download_hashes.csv"
        self.p1 = "autodata_part_0001.zip"
        self.p2 = "autodata_part_0002.zip"
        self.exe = "Autodata__3.45/ADCDA2/ADBCD.exe"
        self.idf = "Autodata__3.45/ADCDA2/COMMON/SAMPLE.IDF"
        self.blocked = "Autodata__3.45/Install-x32.cmd"
        self.manifest = {"package_count": 3, "files": [
            {"path": self.exe, "size_bytes": 4, "chunks": [
                {"package": self.p1, "entry": self.exe, "bytes": 4, "sha256": sha(b"ABCD")}]},
            {"path": self.idf, "size_bytes": 4, "chunks": [
                {"package": self.p1, "entry": self.idf + ".chunk0", "bytes": 2, "sha256": sha(b"AA")},
                {"package": self.p2, "entry": self.idf + ".chunk1", "bytes": 2, "sha256": sha(b"BB")}]},
            {"path": self.blocked, "size_bytes": 3, "chunks": [
                {"package": BLOCKED_PACKAGE, "entry": self.blocked, "bytes": 3, "sha256": sha(b"BAD")}]},
        ]}
        self.audit = [
            dict(zip(FIELDS, (self.exe, "4", "4", sha(b"ABCD"), "1", "PASS", "", "other"))),
            dict(zip(FIELDS, (self.idf, "4", "4", sha(b"AABB"), "2", "PASS", "", "idf"))),
            dict(zip(FIELDS, (self.blocked, "3", "0", "", "1", "FAIL_OR_UNAVAILABLE", "missing", "other"))),
        ]
        self.downloads = [
            {"name": self.p1, "bytes": "100", "sha256": sha(b"ZIP1"), "status": "downloaded"},
            {"name": self.p2, "bytes": "200", "sha256": sha(b"ZIP2"), "status": "downloaded"},
        ]
        self.write()

    def write(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        inventory_bytes = self.manifest_path.read_bytes()
        rows = [{"name": "INVENTAR.json", "bytes": str(len(inventory_bytes)),
                 "sha256": sha(inventory_bytes), "status": "downloaded"}] + self.downloads
        with self.downloads_path.open("w", encoding="utf-8", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=DOWNLOAD_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        with self.reconstructed_path.open("w", encoding="utf-8", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(self.audit)

    def check(self):
        return crosscheck(self.manifest_path, self.reconstructed_path, self.downloads_path)

    def test_valid_records_report_only_aggregate_evidence(self):
        report = self.check()
        self.assertEqual(report["record_consistency"], "PASS")
        self.assertEqual(report["reconstruction_pass_records_consistent"], 2)
        self.assertEqual(report["reconstruction_unavailable_records_consistent"], 1)
        self.assertEqual(report["idf_pass_records_consistent"], 1)
        self.assertEqual(report["single_chunk_reconstructed_hashes_matching_manifest"], 1)
        self.assertEqual(report["multichunk_full_hashes_not_comparable_to_manifest"], 1)
        self.assertFalse(report["bytes_rehashed_in_this_run"])
        self.assertNotIn(self.exe, json.dumps(report))

    def test_tampered_single_chunk_digest_rejected(self):
        self.audit[0]["sha256_reconstructed"] = sha(b"EVIL")
        self.write()
        with self.assertRaisesRegex(ValueError, "Single-chunk hash"):
            self.check()

    def test_forged_pass_on_blocked_file_rejected(self):
        self.audit[2].update(status="PASS", actual_size="3", sha256_reconstructed=sha(b"BAD"), problems="")
        self.write()
        with self.assertRaisesRegex(ValueError, "Unavailable file"):
            self.check()

    def test_blocked_package_download_record_is_rejected(self):
        self.downloads.append({"name": BLOCKED_PACKAGE, "bytes": "100",
                               "sha256": sha(b"BADZIP"), "status": "downloaded"})
        self.write()
        with self.assertRaisesRegex(ValueError, "blocked package"):
            self.check()

    def test_missing_audit_row_rejected(self):
        self.audit.pop()
        self.write()
        with self.assertRaisesRegex(ValueError, "rows do not match"):
            self.check()

    def test_wrong_manifest_sha_rejected(self):
        self.write()
        rows = self.downloads_path.read_text(encoding="utf-8").replace(
            sha(self.manifest_path.read_bytes()), "f" * 64)
        self.downloads_path.write_text(rows, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Manifest download evidence"):
            self.check()

    def test_wrong_chunk_count_rejected(self):
        self.audit[1]["chunk_count"] = "1"
        self.write()
        with self.assertRaisesRegex(ValueError, "chunk count"):
            self.check()


if __name__ == "__main__":
    unittest.main()
