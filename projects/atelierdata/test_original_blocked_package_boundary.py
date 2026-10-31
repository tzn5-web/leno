"""Synthetic regression tests for the non-overridable malware-flagged ZIP policy.

These tests never download, open, or execute any original Autodata file.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from original_archive_preflight import BLOCKED_PACKAGE, audit
from original_installation_readiness import analyze_manifest, build_report, ENTRY
from original_runtime_dependency_audit import _verified_pe


def _row(path, package):
    return {"path": path, "size_bytes": 4, "chunks": [
        {"package": package, "entry": path, "bytes": 4, "sha256": "a" * 64}
    ]}


class BlockedPackageBoundaryTests(unittest.TestCase):
    def test_manifest_presence_never_marks_blocked_installer_available(self):
        installer = "Autodata__3.45/Install-x32.cmd"
        manifest = {"package_count": 2, "files": [
            _row(ENTRY, "autodata_part_0001.zip"),
            _row(installer, BLOCKED_PACKAGE),
        ]}
        report = analyze_manifest(manifest, {"autodata_part_0001.zip", BLOCKED_PACKAGE})
        self.assertEqual(report["available_package_count"], 1)
        self.assertIn(BLOCKED_PACKAGE, report["unavailable_packages"])
        self.assertEqual(report["named_installer_entries_accessible"], 0)
        self.assertFalse(report["license_checked"])

    def test_dependency_reader_refuses_blocked_before_file_probe(self):
        row = _row("Autodata__3.45/ADCDA2/SentinelKeyW.DLL", BLOCKED_PACKAGE)
        with mock.patch.object(Path, "is_file", side_effect=AssertionError("filesystem probe")):
            status, pe = _verified_pe(row, Path("/not-accessed"), ("SENTINELKEYW.DLL",))
        self.assertEqual(status, "package_unavailable")
        self.assertIsNone(pe)

    def test_readiness_skips_blocked_even_when_local_file_exists(self):
        manifest = {"package_count": 1, "files": [_row(ENTRY, BLOCKED_PACKAGE)]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = root / "INVENTAR.json"
            inventory.write_text(json.dumps(manifest), encoding="utf-8")
            (root / BLOCKED_PACKAGE).write_bytes(b"UNTRUSTED-NOT-A-ZIP")
            original = Path.is_file
            def guard(path):
                if path.name == BLOCKED_PACKAGE:
                    raise AssertionError("blocked package was probed")
                return original(path)
            with mock.patch.object(Path, "is_file", autospec=True, side_effect=guard):
                report = build_report(inventory, root)
            self.assertEqual(report["available_package_count"], 0)
            self.assertEqual(report["main_executable"]["status"], "package_unavailable")
            self.assertNotIn("static_runtime_evidence", report)

    def test_archive_preflight_skips_blocked_file_without_opening(self):
        manifest = {"package_count": 1, "files": [_row(ENTRY, BLOCKED_PACKAGE)]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = root / "INVENTAR.json"
            inventory.write_text(json.dumps(manifest), encoding="utf-8")
            (root / BLOCKED_PACKAGE).write_bytes(b"UNTRUSTED-NOT-A-ZIP")
            with mock.patch("zipfile.ZipFile", side_effect=AssertionError("blocked ZIP opened")):
                report = audit(inventory, root)
            self.assertEqual(report["verified_chunk_count"], 0)
            self.assertEqual(report["missing_packages"], [BLOCKED_PACKAGE])
            self.assertFalse(report["complete_archive"])


if __name__ == "__main__":
    unittest.main()
