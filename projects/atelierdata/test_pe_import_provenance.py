"""Synthetic-only PE32 provenance regressions; no original binaries."""
import struct
import unittest

from pe_file_io_xrefs import parse_pe32
from test_pe_file_io_xrefs import sample_pe


class PEImportProvenanceTests(unittest.TestCase):
    def test_baseline_fixture_is_valid(self):
        self.assertEqual(len(parse_pe32(sample_pe())["imports"]), 1)

    def test_raw_alias_with_distinct_rva_rejected(self):
        data = bytearray(sample_pe())
        # Add a third initialized section claiming the same file-backed bytes
        # as .idata, but at a different RVA.
        struct.pack_into("<H", data, 0x86, 3)
        sec = 0x98 + 224 + 2 * 40
        data[sec:sec + 8] = b".alias\0\0"
        struct.pack_into("<IIII", data, sec + 8, 0x80, 0x3000, 0x80, 0x400)
        with self.assertRaisesRegex(ValueError, "raw data"):
            parse_pe32(data)

    def test_initialized_section_header_alias_rejected(self):
        data = bytearray(sample_pe())
        # A second section's RVA is distinct but its raw bytes alias headers.
        struct.pack_into("<I", data, 0x178 + 40 + 20, 0x100)
        with self.assertRaisesRegex(ValueError, "header bytes"):
            parse_pe32(data)

    def test_missing_null_import_descriptor_rejected(self):
        data = bytearray(sample_pe())
        # Both descriptor slots are populated; the declared directory has no
        # zero descriptor. Use a distinct FirstThunk to avoid IAT collision.
        data[0x434:0x448] = data[0x420:0x434]
        struct.pack_into("<I", data, 0x434 + 16, 0x20c8)
        with self.assertRaisesRegex(ValueError, "terminating descriptor"):
            parse_pe32(data)

    def test_duplicate_iat_slot_attribution_rejected(self):
        data = bytearray(sample_pe())
        # Two descriptors share FirstThunk, followed by a zero descriptor.
        struct.pack_into("<I", data, 0x98 + 108, 60)
        data[0x434:0x448] = data[0x420:0x434]
        with self.assertRaisesRegex(ValueError, "Duplicate IAT slot"):
            parse_pe32(data)


if __name__ == "__main__":
    unittest.main()
