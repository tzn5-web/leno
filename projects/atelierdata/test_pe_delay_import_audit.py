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

    def test_ordinal_import(self):
        blob = bytearray(delay_fixture())
        struct.pack_into("<I", blob, 0x570, 0x8000007b)
        public, private = analyze_delay_imports(bytes(blob), hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARSED")
        self.assertEqual(private["descriptors"][0]["symbols"], ["#123"])

    def test_small_directory_is_partial(self):
        blob = bytearray(delay_fixture())
        struct.pack_into("<II", blob, 0x98 + 96 + 13 * 8, 0x2100, 16)
        public, _ = analyze_delay_imports(bytes(blob), hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARTIAL")
        self.assertEqual(public["issue_counts"]["directory_too_small"], 1)

    def test_unmapped_name_is_partial_not_crash(self):
        blob = delay_fixture(malformed=True)
        public, private = analyze_delay_imports(blob, hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARTIAL")
        self.assertEqual(public["issue_counts"]["dll_name_unmapped"], 1)
        self.assertEqual(public["resolved_symbol_count"], 1)
        self.assertIsNone(private["descriptors"][0]["dll"])

    def test_unmapped_directory(self):
        blob = bytearray(delay_fixture())
        struct.pack_into("<II", blob, 0x98 + 96 + 13 * 8, 0x21f0, 64)
        public, _ = analyze_delay_imports(bytes(blob), hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARTIAL")
        self.assertGreater(public["issue_counts"]["directory_unmapped"], 0)

    def test_half_populated_delay_directory_is_partial_not_absent(self):
        for directory_rva, directory_size in ((0x2100, 0), (0, 64)):
            with self.subTest(rva=directory_rva, size=directory_size):
                blob = bytearray(delay_fixture())
                struct.pack_into("<II", blob, 0x98 + 96 + 13 * 8,
                                 directory_rva, directory_size)
                public, private = analyze_delay_imports(
                    bytes(blob), hashlib.sha256(blob).hexdigest())
                self.assertEqual(public["state"], "PARTIAL")
                self.assertEqual(
                    public["issue_counts"]["directory_rva_size_inconsistent"], 1)
                self.assertEqual(public["descriptor_count"], 0)
                self.assertEqual(private["descriptors"], [])

    def test_delay_directory_rva_extent_overflow_is_partial(self):
        blob = bytearray(delay_fixture())
        struct.pack_into("<II", blob, 0x98 + 96 + 13 * 8,
                         0xfffffff0, 64)
        public, _ = analyze_delay_imports(
            bytes(blob), hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARTIAL")
        self.assertEqual(
            public["issue_counts"]["directory_extent_overflows_rva"], 1)

    def test_trailing_directory_bytes_are_not_silently_complete(self):
        blob = bytearray(delay_fixture())
        struct.pack_into("<II", blob, 0x98 + 96 + 13 * 8, 0x2100, 65)
        public, private = analyze_delay_imports(
            bytes(blob), hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARTIAL")
        self.assertEqual(public["issue_counts"]["directory_trailing_bytes"], 1)
        self.assertEqual(private["descriptors"][0]["symbols"], ["MessageBoxA"])

    def test_delay_descriptor_in_raw_file_padding_is_unmapped(self):
        blob = bytearray(delay_fixture())
        # .idata has 0x200 raw bytes but only 0x100 mapped virtual bytes.
        # The directory at RVA 0x2100 is therefore entirely raw padding.
        idata_section = 0x98 + 224 + 40
        struct.pack_into("<I", blob, idata_section + 8, 0x100)
        public, private = analyze_delay_imports(
            bytes(blob), hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARTIAL")
        self.assertEqual(public["issue_counts"]["directory_unmapped"], 1)
        self.assertEqual(private["descriptors"], [])

    def test_dll_name_terminator_in_raw_padding_is_not_mapped(self):
        blob = bytearray(delay_fixture())
        # .idata starts at RVA 0x2100, file offset 0x500. The DLL
        # name begins at RVA 0x2150. Map only its first ten bytes,
        # leaving its NUL byte in the raw-file alignment padding.
        idata_section = 0x98 + 224 + 40
        struct.pack_into("<I", blob, idata_section + 8, 0x5a)
        public, private = analyze_delay_imports(
            bytes(blob), hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARTIAL")
        self.assertEqual(public["issue_counts"]["dll_name_unmapped"], 1)
        self.assertIsNone(private["descriptors"][0]["dll"])

    def test_symbol_name_terminator_in_raw_padding_is_not_mapped(self):
        blob = bytearray(delay_fixture())
        # The imported name is at RVA 0x2192, with its NUL byte
        # at RVA 0x219d. Keep the hint, thunk, and all preceding
        # name bytes mapped, but not the final terminator.
        idata_section = 0x98 + 224 + 40
        struct.pack_into("<I", blob, idata_section + 8, 0x9d)
        public, private = analyze_delay_imports(
            bytes(blob), hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARTIAL")
        self.assertEqual(public["issue_counts"]["thunk_unmapped"], 1)
        self.assertEqual(public["resolved_symbol_count"], 0)
        self.assertEqual(private["descriptors"][0]["dll"], "USER32.dll")
        self.assertEqual(private["descriptors"][0]["symbols"], [])

    def test_symbol_name_null_inside_virtual_extent_is_accepted(self):
        blob = bytearray(delay_fixture())
        idata_section = 0x98 + 224 + 40
        struct.pack_into("<I", blob, idata_section + 8, 0x9e)
        public, private = analyze_delay_imports(
            bytes(blob), hashlib.sha256(blob).hexdigest())
        self.assertEqual(public["state"], "PARSED")
        self.assertEqual(private["descriptors"][0]["symbols"], ["MessageBoxA"])

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
            with self.assertRaisesRegex(ValueError, "must differ"):
                run(src, hashlib.sha256(blob).hexdigest(), src, priv)
            with self.assertRaisesRegex(ValueError, "must differ"):
                run(src, hashlib.sha256(blob).hexdigest(), pub, src)
            self.assertEqual(src.read_bytes(), blob)


if __name__ == "__main__":
    unittest.main()
