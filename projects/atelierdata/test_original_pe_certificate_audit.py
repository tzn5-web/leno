"""Regression tests use only inert synthetic PE headers and ZIP members."""
import hashlib
import json
import struct
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from original_pe_certificate_audit import (
    ALLOWED, BLOCKED, ROOT, assess, inspect_certificate_table)


def synthetic_pe(certificate=False, malformed=False, pe_plus=False):
    data = bytearray(1024)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3c, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x14c)
    struct.pack_into("<H", data, 0x94, 0xf0 if pe_plus else 0xe0)
    opt = 0x98
    struct.pack_into("<H", data, opt, 0x20b if pe_plus else 0x10b)
    struct.pack_into("<I", data, opt + (108 if pe_plus else 92), 16)
    if certificate:
        dd = opt + (112 if pe_plus else 96)
        struct.pack_into("<II", data, dd + 32, 768, 24)
        struct.pack_into("<IHH", data, 768, 999 if malformed else 17, 0x200, 2)
        data[776:785] = b"FAKEPKCS7"
    return bytes(data)


def fixture(folder, cert_for=(), corrupt=None):
    rows = []
    with zipfile.ZipFile(folder / "autodata_part_0001.zip", "w") as z:
        for name in ALLOWED:
            data = synthetic_pe(certificate=name in cert_for)
            path = ROOT + name
            rows.append({"path": path, "size_bytes": len(data), "chunks": [
                {"package": "autodata_part_0001.zip", "entry": path,
                 "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}]})
            z.writestr(path, b"TAMPERED" if corrupt == name else data)
    manifest = folder / "INVENTAR.json"
    manifest.write_text(json.dumps({"files": rows, "package_count": 1}), encoding="utf-8")
    return manifest


class CertificateTests(unittest.TestCase):
    def test_no_certificate_table_is_not_authenticity(self):
        result = inspect_certificate_table(synthetic_pe())
        self.assertEqual(result["certificate_table"], "absent")
        self.assertFalse(result["authenticode_verified"])

    def test_pkcs7_container_not_trust(self):
        result = inspect_certificate_table(synthetic_pe(certificate=True))
        self.assertEqual(result["pkcs7_container_count"], 1)
        self.assertFalse(result["authenticode_verified"])

    def test_pe32_plus_security_directory_uses_file_offset(self):
        result = inspect_certificate_table(synthetic_pe(certificate=True, pe_plus=True))
        self.assertEqual(result["pe_format"], "PE32+")
        self.assertEqual(result["pkcs7_container_count"], 1)

    def test_invalid_win_certificate_length_rejected(self):
        with self.assertRaisesRegex(ValueError, "WIN_CERTIFICATE length"):
            inspect_certificate_table(synthetic_pe(certificate=True, malformed=True))

    def test_security_directory_out_of_file_rejected(self):
        data = bytearray(synthetic_pe(certificate=True))
        struct.pack_into("<II", data, 0x98 + 96 + 32, 4096, 24)
        with self.assertRaisesRegex(ValueError, "outside file"):
            inspect_certificate_table(bytes(data))

    def test_not_pe_rejected(self):
        with self.assertRaisesRegex(ValueError, "DOS signature"):
            inspect_certificate_table(b"NOT-PE")

    def test_all_five_verified_without_claiming_trust(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root, cert_for=("RelLic.dll", "ChilkatCert.dll"))
            result = assess(manifest, root)
            self.assertEqual(result["verified_component_count"], 5)
            self.assertEqual(result["embedded_pkcs7_components"], 2)
            self.assertEqual(result["unsigned_certificate_table_components"], 3)
            self.assertFalse(result["publisher_signature_cryptographically_verified"])
            self.assertFalse(result["installation_ready"])

    def test_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root, corrupt="ADBCD.exe")
            with self.assertRaisesRegex(ValueError, "size|SHA256"):
                assess(manifest, root)

    def test_blocked_package_never_opened(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            (root / BLOCKED).write_bytes(b"UNTRUSTED-DO-NOT-READ")
            with self.assertRaisesRegex(ValueError, "Blocked package"):
                assess(manifest, root)

    def test_blocked_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            try:
                (root / BLOCKED).symlink_to(root / "autodata_part_0001.zip")
            except OSError:
                self.skipTest("Symlink creation unavailable on this Windows runner")
            with self.assertRaisesRegex(ValueError, "Blocked package"):
                assess(manifest, root)

    def test_duplicate_zip_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = fixture(root)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(root / "autodata_part_0001.zip", "a") as z:
                    z.writestr(ROOT + "ADBCD.exe", synthetic_pe())
            with self.assertRaisesRegex(ValueError, "duplicate"):
                assess(manifest, root)


if __name__ == "__main__":
    unittest.main()
