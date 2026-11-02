"""Synthetic-only regression for PE API string triage."""
import unittest
from pe_literal_evidence import mapped_literal_positions


class LiteralEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(640)
        self.sections = [{'raw_at': 64, 'raw_size': 256, 'vsize': 200, 'rva': 0x1000},
                         {'raw_at': 384, 'raw_size': 128, 'vsize': 128, 'rva': 0x2000}]

    def scan(self, term='ReadFile', encoding='ascii', limit=1024):
        return mapped_literal_positions(bytes(self.data), self.sections, term, encoding, limit)

    def test_exact_terminated_ascii(self):
        self.data[80:89] = b'ReadFile\0'
        self.assertEqual(self.scan(), ([(80, 0x1010)], False))

    def test_rejects_suffix_and_embedded_prefix(self):
        self.data[80:90] = b'ReadFileX\0'
        self.data[110:122] = b'SomeReadFile\0'
        self.assertEqual(self.scan(), ([], False))

    def test_rejects_virtual_tail_overlay_and_header(self):
        self.data[256:265] = b'ReadFile\0'
        self.data[520:529] = b'ReadFile\0'
        self.data[10:19] = b'ReadFile\0'
        self.assertEqual(self.scan(), ([], False))

    def test_utf16le_requires_two_byte_terminator(self):
        raw = 'ReadFile'.encode('utf-16le')
        self.data[90:90+len(raw)+2] = raw + b'\0\0'
        self.assertEqual(self.scan(encoding='utf-16le'), ([(90, 0x101a)], False))
        self.data[90+len(raw):90+len(raw)+2] = b'X\0'
        self.assertEqual(self.scan(encoding='utf-16le'), ([], False))

    def test_utf16le_embedded_word_rejected(self):
        raw = 'AReadFile\0'.encode('utf-16le')
        self.data[90:90+len(raw)] = raw
        self.assertEqual(self.scan(encoding='utf-16le'), ([], False))

    def test_truncation_only_when_extra_qualified_hit_exists(self):
        self.data[80:89] = b'ReadFile\0'
        self.assertEqual(self.scan(limit=1), ([(80, 0x1010)], False))
        self.data[100:109] = b'ReadFile\0'
        self.assertEqual(self.scan(limit=1), ([(80, 0x1010)], True))

    def test_unsupported_inputs(self):
        with self.assertRaises(ValueError):
            self.scan(encoding='utf-8')
        with self.assertRaises(ValueError):
            self.scan(limit=0)


if __name__ == '__main__':
    unittest.main()
