"""Synthetic regression tests for strict PE32 file-backed import evidence.

No proprietary executables, IDF content, or private offsets are used.
"""
import hashlib
import struct
import unittest

from pe_file_io_xrefs import analyze, parse_pe32
from test_pe_file_io_xrefs import sample_pe


OPT = 0x98
IDATA = OPT + 224 + 40
TEXT = OPT + 224


class StrictPEImportMappingTests(unittest.TestCase):
    def test_dll_name_terminator_in_raw_padding_rejected(self):
        blob = bytearray(sample_pe())
        # DLL string at RVA 0x2080; its terminating NUL is at 0x208c.
        struct.pack_into("<I", blob, IDATA + 8, 0x8c)
        with self.assertRaisesRegex(ValueError, "mapped"):
            parse_pe32(bytes(blob))

    def test_symbol_name_terminator_in_raw_padding_rejected(self):
        blob = bytearray(sample_pe())
        # The LoadLibraryA terminator is outside the mapped .idata extent.
        struct.pack_into("<I", blob, IDATA + 8, 0xee)
        with self.assertRaisesRegex(ValueError, "mapped"):
            parse_pe32(bytes(blob))

    def test_valid_name_terminators_remain_accepted(self):
        blob = sample_pe()
        pe = parse_pe32(blob)
        self.assertEqual(pe["imports"][0x4020c0]["symbol"], "LoadLibraryA")

    def test_overlapping_section_rvas_are_not_resolved_by_order(self):
        blob = bytearray(sample_pe())
        struct.pack_into("<I", blob, TEXT + 12, 0x2000)
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            parse_pe32(bytes(blob))

    def test_directory_cannot_borrow_terminator_beyond_declared_size(self):
        blob = bytearray(sample_pe())
        struct.pack_into("<I", blob, OPT + 108, 20)
        with self.assertRaisesRegex(ValueError, "directory extent"):
            parse_pe32(bytes(blob))

    def test_half_populated_import_directory_rejected(self):
        blob = bytearray(sample_pe())
        struct.pack_into("<I", blob, OPT + 108, 0)
        with self.assertRaisesRegex(ValueError, "Half-populated"):
            parse_pe32(bytes(blob))

    def test_ff15_in_raw_alignment_padding_not_counted_as_callsite(self):
        blob = bytearray(sample_pe())
        # FF15 begins at .text offset 0x20, exactly outside VirtualSize.
        struct.pack_into("<I", blob, TEXT + 8, 0x20)
        data = bytes(blob)
        public, private = analyze(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(public["candidate_count"], 0)
        self.assertEqual(public["executable_bytes_scanned"], 0x20)
        self.assertEqual(private["candidates"], [])

    def test_mapped_ff15_still_counted(self):
        data = sample_pe()
        public, _ = analyze(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(public["candidate_count"], 1)


if __name__ == "__main__":
    unittest.main()
