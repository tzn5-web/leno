"""Synthetic-only PE32 regressions for IDF extension versus API literals.

These tests contain no original Autodata bytes or proprietary records.
"""
import hashlib
import struct
import unittest

from pe_file_io_xrefs import analyze
from pe_literal_evidence import mapped_literal_positions
from test_pe_file_io_xrefs import sample_pe


def public_scan(data):
    data = bytes(data)
    return analyze(data, hashlib.sha256(data).hexdigest())[0]


def extension_count(report, encoding="ascii"):
    return report["literal_probes"][".IDF"][encoding]["literal_count_at_most_1024"]


class IDFExtensionLiteralTests(unittest.TestCase):
    def test_ascii_filename_extension_with_word_prefix(self):
        blob = bytearray(sample_pe())
        name = b"C:\\COMMON\\MODELS.IDF\0"
        blob[0x260:0x260 + len(name)] = name
        report = public_scan(blob)
        self.assertEqual(extension_count(report), 1)
        self.assertFalse(report["idf_decoder_proven"])

    def test_mixed_case_filename_extension(self):
        blob = bytearray(sample_pe())
        name = b"models.iDf\0"
        blob[0x260:0x260 + len(name)] = name
        self.assertEqual(extension_count(public_scan(blob)), 1)

    def test_utf16_filename_extension_with_word_prefix(self):
        blob = bytearray(sample_pe())
        name = "C:\\DATA\\DTC.Idf\0".encode("utf-16le")
        blob[0x260:0x260 + len(name)] = name
        self.assertEqual(extension_count(public_scan(blob), "utf-16le"), 1)

    def test_extension_must_end_with_nul(self):
        blob = bytearray(sample_pe())
        name = b"MODELS.IDFX\0"
        blob[0x260:0x260 + len(name)] = name
        self.assertEqual(extension_count(public_scan(blob)), 0)

    def test_unbacked_section_padding_is_not_evidence(self):
        blob = bytearray(sample_pe())
        name = b"MODELS.IDF\0"
        blob[0x260:0x260 + len(name)] = name
        text_header = 0x98 + 224
        struct.pack_into("<I", blob, text_header + 8, 0x60)
        self.assertEqual(extension_count(public_scan(blob)), 0)

    def test_api_word_prefix_remains_rejected(self):
        blob = bytearray(sample_pe())
        name = b"OtherReadFile\0"
        blob[0x260:0x260 + len(name)] = name
        report = public_scan(blob)
        self.assertEqual(report["literal_probes"]["ReadFile"]["ascii"]["literal_count_at_most_1024"], 0)

    def test_api_case_matching_remains_strict(self):
        blob = bytearray(sample_pe())
        name = b"readfile\0"
        blob[0x260:0x260 + len(name)] = name
        report = public_scan(blob)
        self.assertEqual(report["literal_probes"]["ReadFile"]["ascii"]["literal_count_at_most_1024"], 0)

    def test_direct_scanner_default_stays_strict(self):
        raw = b"MODELS.IDF\0"
        sections = [{"raw_at": 0, "raw_size": len(raw), "vsize": len(raw), "rva": 0x1000}]
        self.assertEqual(mapped_literal_positions(raw, sections, ".IDF", "ascii"), ([], False))
        self.assertEqual(mapped_literal_positions(raw, sections, ".IDF", "ascii",
                                                  allow_word_prefix=True), ([(6, 0x1006)], False))
        self.assertEqual(mapped_literal_positions(raw.lower(), sections, ".IDF", "ascii",
                                                  allow_word_prefix=True, case_insensitive=True),
                         ([(6, 0x1006)], False))

    def test_invalid_policy_flags_rejected(self):
        with self.assertRaises(ValueError):
            mapped_literal_positions(b".IDF\0", [{"raw_at": 0, "raw_size": 5,
                                      "vsize": 5, "rva": 0x1000}], ".IDF", "ascii",
                                     allow_word_prefix=1)


if __name__ == "__main__":
    unittest.main()
