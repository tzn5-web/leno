"""Synthetic-only UTF-16LE literal boundary regressions; no original binaries."""
import unittest

from pe_literal_evidence import mapped_literal_positions


class UnicodeLiteralBoundaryTests(unittest.TestCase):
    def scan(self, value):
        data = bytearray(256)
        raw = value.encode("utf-16le") + b"\x00\x00"
        data[32:32 + len(raw)] = raw
        sections = [{"raw_at": 32, "raw_size": 128, "vsize": 128, "rva": 0x1000}]
        return mapped_literal_positions(bytes(data), sections, "ReadFile", "utf-16le")

    def test_standalone_literal(self):
        self.assertEqual(self.scan("ReadFile"), ([(32, 0x1000)], False))

    def test_latin_unicode_word_prefix(self):
        self.assertEqual(self.scan("éReadFile"), ([], False))

    def test_greek_unicode_word_prefix(self):
        self.assertEqual(self.scan("ΩReadFile"), ([], False))

    def test_cjk_unicode_word_prefix(self):
        self.assertEqual(self.scan("漢ReadFile"), ([], False))

    def test_underscore_prefix(self):
        self.assertEqual(self.scan("_ReadFile"), ([], False))

    def test_punctuation_is_not_word_prefix(self):
        self.assertEqual(self.scan("!ReadFile"), ([(34, 0x1002)], False))


if __name__ == "__main__":
    unittest.main()
