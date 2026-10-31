"""Synthetic fixtures only: ZIP structure and strict blocked-package boundary."""
import os
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

from original_zip_container_audit import BLOCKED_PACKAGE, audit, expected_parts

PACKAGE = "autodata_part_0001.zip"
ENTRY = "Synthetic/data.bin"


def manifest(size=3):
    return {"files": [
        {"path": ENTRY, "chunks": [{"package": PACKAGE, "entry": ENTRY, "bytes": size}]},
        {"path": "Synthetic/blocked", "chunks": [
            {"package": BLOCKED_PACKAGE, "entry": "Synthetic/blocked", "bytes": 3}]}
    ]}


class OriginalZipContainerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        with zipfile.ZipFile(self.root / PACKAGE, "w") as z:
            z.writestr(ENTRY, b"abc")

    def result(self, m=None):
        return audit(m or manifest(), self.root)

    def errors(self):
        return self.result()["packages"][PACKAGE]["errors"]

    def test_valid_metadata_not_sha256_proof(self):
        result = self.result()
        self.assertEqual(result["counts"]["verified_structure_only"], 1)
        self.assertFalse(result["sha256_verified_by_this_audit"])
        self.assertFalse(result["payloads_decompressed"])

    def test_blocked_directory_never_probed(self):
        (self.root / BLOCKED_PACKAGE).mkdir()
        result = self.result()
        self.assertEqual(result["packages"][BLOCKED_PACKAGE]["status"], "blocked_not_accessed")

    def test_missing_package(self):
        (self.root / PACKAGE).unlink()
        self.assertEqual(self.result()["counts"]["missing"], 1)

    def test_unexpected_member(self):
        with zipfile.ZipFile(self.root / PACKAGE, "a") as z:
            z.writestr("Synthetic/extra", b"1")
        self.assertIn("unexpected_member", self.errors())

    def test_size_mismatch(self):
        self.assertIn("manifest_size_mismatch", self.result(manifest(4))["packages"][PACKAGE]["errors"])

    def test_duplicate_member(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.root / PACKAGE, "a") as z:
                z.writestr(ENTRY, b"abc")
        self.assertIn("duplicate_casefold_member", self.errors())

    def test_symlink_member(self):
        info = zipfile.ZipInfo(ENTRY)
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        with zipfile.ZipFile(self.root / PACKAGE, "w") as z:
            z.writestr(info, b"abc")
        self.assertIn("symlink_member", self.errors())

    def test_encrypted_flag_without_decryption(self):
        path = self.root / PACKAGE
        raw = bytearray(path.read_bytes())
        raw[6] |= 1
        central = raw.find(b"PK\x01\x02")
        self.assertGreater(central, 0)
        raw[central + 8] |= 1
        path.write_bytes(raw)
        self.assertIn("encrypted_member", self.errors())

    def test_local_filename_mismatch(self):
        path = self.root / PACKAGE
        raw = bytearray(path.read_bytes())
        raw[30] = ord("X")
        path.write_bytes(raw)
        self.assertIn("local_name_mismatch", self.errors())

    def test_unsafe_manifest_path(self):
        m = manifest()
        m["files"][0]["chunks"][0]["entry"] = "../escape"
        with self.assertRaises(ValueError):
            self.result(m)

    def test_blocked_manifest_entry_mandatory(self):
        with self.assertRaises(ValueError):
            expected_parts({"files": manifest()["files"][:1]})

    def test_symlink_package(self):
        target = self.root / "real.zip"
        (self.root / PACKAGE).rename(target)
        try:
            (self.root / PACKAGE).symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink unavailable on runner")
        self.assertIn("symlink_package", self.errors())

    def test_manifest_case_collision(self):
        m = manifest()
        m["files"].append({"path": "Synthetic/DATA.bin", "chunks": [
            {"package": PACKAGE, "entry": "Synthetic/DATA.bin", "bytes": 3}]})
        with self.assertRaises(ValueError):
            expected_parts(m)


if __name__ == "__main__":
    unittest.main()
