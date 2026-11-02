"""Synthetic PE-section alias regression: no original/proprietary bytes."""
import unittest
from pe_literal_evidence import mapped_literal_positions


class SectionAliasTests(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(640)
        self.data[80:89] = b'ReadFile\0'
        self.first = {'raw_at': 64, 'raw_size': 128, 'vsize': 128, 'rva': 0x1000}

    def scan(self, sections):
        return mapped_literal_positions(bytes(self.data), sections, 'ReadFile', 'ascii')

    def test_single_section(self):
        self.assertEqual(self.scan([self.first]), ([(80, 0x1010)], False))

    def test_same_rva_different_raw_section(self):
        second = {'raw_at': 320, 'raw_size': 64, 'vsize': 64, 'rva': 0x1008}
        self.assertEqual(self.scan([self.first, second]), ([], False))

    def test_same_raw_different_rva_section(self):
        second = {'raw_at': 72, 'raw_size': 64, 'vsize': 64, 'rva': 0x3000}
        self.assertEqual(self.scan([self.first, second]), ([], False))

    def test_adjacent_disjoint_sections(self):
        second = {'raw_at': 192, 'raw_size': 64, 'vsize': 64, 'rva': 0x1080}
        self.assertEqual(self.scan([self.first, second]), ([(80, 0x1010)], False))

    def test_partial_virtual_alias_only_at_terminator(self):
        second = {'raw_at': 320, 'raw_size': 64, 'vsize': 64, 'rva': 0x1018}
        self.assertEqual(self.scan([self.first, second]), ([], False))

    def test_raw_alias_of_terminator(self):
        second = {'raw_at': 88, 'raw_size': 64, 'vsize': 64, 'rva': 0x3000}
        self.assertEqual(self.scan([self.first, second]), ([], False))


if __name__ == '__main__':
    unittest.main()
