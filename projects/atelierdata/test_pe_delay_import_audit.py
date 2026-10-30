"""Synthetic tests for PE delay imports; no original proprietary binary in CI."""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from pe_delay_import_audit import analyze_delay_imports, run
from test_pe_file_io_xrefs import sample_pe


def delay_fixture(va_mode=False, malformed=False):
    data = bytearray(sample_pe())
    optional = 0x98
    struct.pack_into("<II", data, optional + 96 + 13 * 8, 0x2100, 64)
    base = 0x400000 if va_mode else 0
    attrs = 0 if va_mode else 1
    name = 0xfffffff0 if malformed else base + 0x2150
    struct.pack_into("<8I", data, 0x500, attrs, name, 0, base + 0x2180,
                     base + 0x2170, 0, 0, 0)
    data[0x550:0x55b] = b"USER32.dll\0"
    struct.pack_into("<II", data, 0x570, base + 0x2190, 0)
    data[0x592:0x59e] = b"MessageBoxA\0"
    return bytes(data)


class DelayImportAuditTests(unittest.TestCase):
    def test_no_delay_directory(self):
        blob = sample_pe()
        public, private = analyze_delay_imports(blob, hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "ABSENT")
        self.assertEqual(public["descriptor_count"], 0)
        self.assertEqual(private["descriptors"], [])

    def test_rva_delay_descriptor(self):
        blob = delay_fixture()
        public, private = analyze_delay_imports(blob, hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARSED")
        self.assertEqual(public["descriptor_count"], 1)
        self.assertEqual(public["resolved_symbol_count"], 1)
        self.assertEqual(public["pointer_mode_counts"], {"RVA": 1})
        self.assertEqual(private["descriptors"][0]["dll"], "USER32.dll")
        self.assertEqual(private["descriptors"][0]["symbols"], ["MessageBoxA"])
        self.assertNotIn("MessageBoxA", json.dumps(public))
        self.assertNotIn("descriptor_file_offset", json.dumps(public))

    def test_va_delay_descriptor(self):
        blob = delay_fixture(va_mode=True)
        public, private = analyze_delay_imports(blob, hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARSED")
        self.assertEqual(public["pointer_mode_counts"], {"VA": 1})
        self.assertEqual(private["descriptors"][0]["symbols"], ["MessageBoxA"])

    def test_unmapped_name_is_partial_not_crash(self):
        blob = delay_fixture(malformed=True)
        public, private = analyze_delay_imports(blob, hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARTIAL")
        self.assertEqual(public["issue_counts"]["dll_name_unmapped"], 1)
        self.assertEqual(public["resolved_symbol_count"], 1)
        self.assertIsNone(private["descriptors"][0]["dll"])

    def test_truncated_descriptor_directory(self):
        blob = bytearray(delay_fixture())
        struct.pack_into("<II", blob, 0x98 + 96 + 13 * 8, 0x21f0, 64)
        public, _ = analyze_delay_imports(bytes(blob), hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARTIAL")
        self.assertGreater(public["issue_counts"]["descriptor_unmapped"], 0)

    def test_sha256_and_output_separation(self):
        blob = delay_fixture()
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            analyze_delay_imports(blob, "0" * 64)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            src, pub, priv = root / "synthetic.exe", root / "public.json", root / "private.json"
            src.write_bytes(blob)
            result = run(src, hashlib.sha256(blob).hexdigest(), pub, priv)
            self.assertEqual(result["state"], "PARSED")
            self.assertNotIn("MessageBoxA", pub.read_text())
            self.assertIn("MessageBoxA", priv.read_text())
            with self.assertRaisesRegex(ValueError, "must differ"):
                run(src, hashlib.sha256(blob).hexdigest(), pub, pub)


if __name__ == "__main__":
    unittest.main()
