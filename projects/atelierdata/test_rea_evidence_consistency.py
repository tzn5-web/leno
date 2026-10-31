"""Synthetic regression tests: no original Autodata bytes or proprietary data."""
import hashlib
import json
import struct
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from rea_evidence_consistency import reconcile, main, SCHEMA

SHA = "a" * 64


def fixture():
    return {
        "operation": "inspect_pe_imports",
        "subject": {"digest": {"sha256": SHA}},
        "normalized_result": {
            "artifact": {"sha256": SHA, "bytes": 1024},
            "format": "pe32", "machine": 332, "bits": 32,
            "imports": [{"name": "KERNEL32.dll", "functions": [
                {"name": "ReadFile", "iat_rva": 4096},
                {"name": "CloseHandle", "iat_rva": 4100}]}],
            "delay_imports": [
                {"index": 0, "attributes": 1, "name": "other.dll"},
                {"index": 2, "attributes": 0x1234, "name": None}],
            "issues": [{"code": "unsupported_form"}],
            "coverage": {"status": "partial", "imports": 2},
            "delay_import_directory": {"size": 64},
        },
    }


def sample_pe():
    b = bytearray(1536)
    b[:2] = b"MZ"
    struct.pack_into("<I", b, 0x3c, 0x80)
    b[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", b, 0x84, 0x14c, 2, 0, 0, 0, 224, 0x0102)
    opt = 0x98
    struct.pack_into("<H", b, opt, 0x10b)
    struct.pack_into("<I", b, opt + 28, 0x400000)
    struct.pack_into("<I", b, opt + 60, 0x200)
    struct.pack_into("<I", b, opt + 92, 16)
    struct.pack_into("<II", b, opt + 104, 0x2020, 40)
    sec = opt + 224
    b[sec:sec + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", b, sec + 8, 0x200, 0x1000, 0x200, 0x200)
    struct.pack_into("<I", b, sec + 36, 0x60000020)
    sec += 40
    b[sec:sec + 8] = b".idata\0\0"
    struct.pack_into("<IIII", b, sec + 8, 0x200, 0x2000, 0x200, 0x400)
    struct.pack_into("<I", b, sec + 36, 0x40000040)
    struct.pack_into("<IIIII", b, 0x420, 0x20a0, 0, 0, 0x2080, 0x20c0)
    b[0x480:0x48d] = b"KERNEL32.dll\0"
    struct.pack_into("<II", b, 0x4a0, 0x20e0, 0)
    struct.pack_into("<II", b, 0x4c0, 0x20e0, 0)
    b[0x4e2:0x4ee] = b"LoadLibraryA\0"
    return bytes(b)


class ReaEvidenceConsistencyTests(unittest.TestCase):
    def test_aggregate_no_private_addresses(self):
        result = reconcile(fixture(), SHA)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["static_import_function_count"], 2)
        self.assertEqual(result["rea_delay_rows_invalid_attributes"], 1)
        self.assertEqual(result["rea_delay_rows_outside_declared_directory"], 1)
        self.assertFalse(result["original_pe_independently_verified"])
        self.assertNotIn("4096", json.dumps(result))
        self.assertNotIn("other.dll", json.dumps(result))

    def test_wrong_digest_rejected(self):
        with self.assertRaises(ValueError):
            reconcile(fixture(), "b" * 64)

    def test_malformed_digest_rejected(self):
        with self.assertRaises(ValueError):
            reconcile(fixture(), "xyz")

    def test_duplicate_iat_rejected(self):
        x = fixture()
        x["normalized_result"]["imports"][0]["functions"][1]["iat_rva"] = 4096
        with self.assertRaises(ValueError):
            reconcile(x, SHA)

    def test_coverage_mismatch_rejected(self):
        x = fixture()
        x["normalized_result"]["coverage"]["imports"] = 99
        with self.assertRaises(ValueError):
            reconcile(x, SHA)

    def test_duplicate_delay_index_rejected(self):
        x = fixture()
        x["normalized_result"]["delay_imports"][1]["index"] = 0
        with self.assertRaises(ValueError):
            reconcile(x, SHA)

    def test_unknown_issue_rejected(self):
        x = fixture()
        x["normalized_result"]["issues"][0]["code"] = "unknown"
        with self.assertRaises(ValueError):
            reconcile(x, SHA)

    def test_complete_coverage_contradiction_rejected(self):
        x = fixture()
        x["normalized_result"]["coverage"]["status"] = "complete"
        with self.assertRaises(ValueError):
            reconcile(x, SHA)

    def test_pe_sha_required(self):
        with self.assertRaises(ValueError):
            reconcile(fixture(), SHA, b"bad")

    def test_oversized_source_rejected(self):
        x = fixture()
        x["normalized_result"]["artifact"]["bytes"] = 2**31
        with self.assertRaises(ValueError):
            reconcile(x, SHA)

    def test_empty_issues_allowed(self):
        x = fixture()
        x["normalized_result"]["issues"] = []
        x["normalized_result"]["coverage"]["status"] = "complete"
        self.assertEqual(reconcile(x, SHA)["rea_total_issues"], 0)

    def test_independent_synthetic_pe_import_check(self):
        data = sample_pe()
        sha = hashlib.sha256(data).hexdigest()
        x = fixture()
        x["subject"]["digest"]["sha256"] = sha
        x["normalized_result"]["artifact"] = {"sha256": sha, "bytes": len(data)}
        x["normalized_result"]["imports"] = [{"name": "KERNEL32.dll", "functions": [
            {"name": "LoadLibraryA", "iat_rva": 0x20c0}]}]
        x["normalized_result"]["coverage"]["imports"] = 1
        self.assertTrue(reconcile(x, sha, data)["original_pe_independently_verified"])
        x["normalized_result"]["imports"][0]["functions"][0]["name"] = "ReadFile"
        with self.assertRaisesRegex(ValueError, "differs"):
            reconcile(x, sha, data)

    def test_cli_private_input_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "private.json"
            p.write_text(json.dumps(fixture()), encoding="utf-8")
            with patch("sys.argv", ["tool", "--rea-report", str(p),
                                    "--expected-sha256", SHA, "--public-output", str(p)]):
                with self.assertRaises(SystemExit):
                    main()
            self.assertEqual(json.loads(p.read_text())["operation"], "inspect_pe_imports")


if __name__ == "__main__":
    unittest.main()
