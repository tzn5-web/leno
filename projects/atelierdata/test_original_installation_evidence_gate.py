"""Synthetic ZIP regression tests; no proprietary or executable original files."""
import hashlib
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from original_installation_evidence_gate import assess

ROOT = "Autodata__3.45/ADCDA2/"
ONE = "autodata_part_0001.zip"
TWO = "autodata_part_0002.zip"
BLOCKED = "autodata_part_0016.zip"


def fake_pe():
    """Minimal inert PE header, never executable code."""
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3c, 0x80)
    data[0x80:0x84] = b"PE\\0\\0".replace(b"\\0", b"\0")
    struct.pack_into("<H", data, 0x84, 0x14c)
    struct.pack_into("<H", data, 0x86, 0)
    struct.pack_into("<H", data, 0x94, 0xe0)
    struct.pack_into("<H", data, 0x98, 0x10b)
    struct.pack_into("<H", data, 0x98 + 68, 2)
    return bytes(data)


def row(path, package, data):
    return {"path": path, "size_bytes": len(data), "chunks": [
        {"package": package, "entry": path, "bytes": len(data),
         "sha256": hashlib.sha256(data).hexdigest()}]}


def fixture(directory, include_two=False, include_blocked=True, tamper=False,
            extra=False):
    exe = fake_pe()
    idf = b"SYNTHETIC-IDF-DO-NOT-DECODE"
    manifest_rows = [
        row(ROOT + "ADBCD.exe", ONE, exe),
        row(ROOT + "COMMON/CONST.IDF", ONE, idf),
        row(ROOT + "COMMON/VERINFO.DAT", ONE, b"ProductCode=TEST\n"),
    ]
    if include_two:
        manifest_rows.append(row(ROOT + "RelLic.dll", TWO, b"SYNTHETIC"))
    if include_blocked:
        manifest_rows.append(row("Autodata__3.45/Install-x32.cmd", BLOCKED,
                                 b"NEVER EXECUTE"))
    manifest = {"files": manifest_rows,
                "package_count": 1 + int(include_two) + int(include_blocked)}
    path = directory / "INVENTAR.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with zipfile.ZipFile(directory / ONE, "w") as archive:
        archive.writestr(ROOT + "ADBCD.exe", exe)
        archive.writestr(ROOT + "COMMON/CONST.IDF",
                         b"CORRUPTED" if tamper else idf)
        archive.writestr(ROOT + "COMMON/VERINFO.DAT", b"ProductCode=TEST\n")
        if extra:
            archive.writestr(ROOT + "UNEXPECTED.bin", b"EXTRA")
    return path


class EvidenceGateTests(unittest.TestCase):
    def test_authorized_parts_are_verified_but_not_install_ready(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = assess(fixture(root), root)
            self.assertEqual(report["state"],
                             "AVAILABLE_PARTS_VERIFIED_DISTRIBUTION_INCOMPLETE")
            self.assertEqual(report["sha256_verified_chunks_in_available_packages"], 3)
            self.assertEqual(report["expected_chunks_in_available_packages"], 3)
            self.assertEqual(report["idf_sha256_verified"], 1)
            self.assertTrue(report["main_executable_sha256_and_pe_verified"])
            self.assertEqual(report["unavailable_packages"], [BLOCKED])
            self.assertFalse(report["installation_ready"])
            self.assertFalse(report["licensing_proven"])

    def test_tampered_idf_fails_even_when_package_present(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = assess(fixture(root, tamper=True), root)
            self.assertEqual(report["state"], "INTEGRITY_FAILURE")
            self.assertEqual(report["idf_sha256_verified"], 0)
            self.assertTrue(report["errors"])

    def test_unexpected_zip_entry_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = assess(fixture(root, extra=True), root)
            self.assertEqual(report["state"], "INTEGRITY_FAILURE")

    def test_blocked_package_is_never_opened_even_if_present(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            (root / BLOCKED).write_bytes(b"not a ZIP")
            with self.assertRaisesRegex(ValueError, "refuse inspection"):
                assess(manifest, root)

    def test_missing_unblocked_package_is_not_acceptable_partial(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = assess(fixture(root, include_two=True), root)
            self.assertEqual(report["state"], "UNEXPECTED_MISSING_PACKAGES")
            self.assertEqual(report["unexpected_unavailable_packages"], [TWO])

    def test_complete_synthetic_archive_still_not_license_proof(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = assess(fixture(root, include_blocked=False), root)
            self.assertEqual(report["state"],
                             "ALL_DISTRIBUTION_PARTS_INTEGRITY_VERIFIED")
            self.assertFalse(report["installation_ready"])
            self.assertFalse(report["publisher_authenticity_proven"])

    def test_invalid_manifest_package_count_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["package_count"] = 999
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "package_count"):
                assess(manifest, root)


if __name__ == "__main__":
    unittest.main()
