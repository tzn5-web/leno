"""Synthetic-only regression tests for bounded PE32 delay imports."""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from pe_delay_imports import analyze, parse_delay_imports, run
from test_pe_file_io_xrefs import sample_pe


def fixture(*, va=False, ordinal=False):
    data = bytearray(sample_pe())
    opt = 0x98
    struct.pack_into('<II', data, opt + 96 + 13 * 8, 0x2100, 64)
    base = 0x400000 if va else 0
    # IMAGE_DELAYLOAD_DESCRIPTOR in initialized .idata bytes.
    struct.pack_into('<8I', data, 0x500, int(not va), 0x2140 + base,
                     0, 0x2170 + base, 0x2160 + base, 0, 0, 0)
    data[0x540:0x54d] = b'DELAYTEST.dll\0'
    struct.pack_into('<II', data, 0x560,
                     0x8000002a if ordinal else 0x2180 + base, 0)
    struct.pack_into('<II', data, 0x570, 0x12345678, 0)
    struct.pack_into('<H', data, 0x580, 0)
    data[0x582:0x58b] = b'DelayAPI\0'
    return bytes(data)


class DelayImportTests(unittest.TestCase):
    def test_rva_named_import(self):
        data = fixture()
        result, private = analyze(data, hashlib.sha256(data).hexdigest())
        self.assertEqual((result['delay_descriptors'], result['named_symbols'],
                          result['rva_descriptors']), (1, 1, 1))
        self.assertEqual(private['descriptors'][0]['entries'][0]['symbol'], 'DelayAPI')
        self.assertNotIn('DelayAPI', json.dumps(result))
        self.assertFalse(result['idf_decoder_proven'])

    def test_va_ordinal_import(self):
        data = fixture(va=True, ordinal=True)
        result, private = analyze(data, hashlib.sha256(data).hexdigest())
        self.assertEqual((result['ordinal_symbols'], result['va_descriptors']), (1, 1))
        self.assertEqual(private['descriptors'][0]['entries'][0]['symbol'], '#42')

    def test_delay_iat_overlaps_classic_import_rejected(self):
        data = bytearray(fixture())
        # Classic sample_pe() already owns IAT slot 0x20c0.
        struct.pack_into('<I', data, 0x50c, 0x20c0)
        with self.assertRaisesRegex(ValueError, 'duplicate classic/delay IAT slot'):
            parse_delay_imports(data)

    def test_duplicate_delay_iat_across_descriptors_rejected(self):
        data = bytearray(fixture())
        # Relocate DLL string to make room for the third (null) descriptor.
        data[0x5a0:0x5ad] = data[0x540:0x54d]
        data[0x540:0x54d] = bytes(13)
        struct.pack_into('<I', data, 0x504, 0x21a0)
        data[0x520:0x540] = data[0x500:0x520]
        struct.pack_into('<II', data, 0x98 + 96 + 13 * 8, 0x2100, 96)
        with self.assertRaisesRegex(ValueError, 'duplicate classic/delay IAT slot'):
            parse_delay_imports(data)

    def test_distinct_delay_iat_slots_are_accepted(self):
        data = bytearray(fixture())
        data[0x5a0:0x5ad] = data[0x540:0x54d]
        data[0x540:0x54d] = bytes(13)
        struct.pack_into('<I', data, 0x504, 0x21a0)
        data[0x520:0x540] = data[0x500:0x520]
        # Same DLL and name table, but a separate, initialized IAT slot.
        struct.pack_into('<I', data, 0x52c, 0x2190)
        struct.pack_into('<II', data, 0x98 + 96 + 13 * 8, 0x2100, 96)
        result = parse_delay_imports(data)
        self.assertEqual(len(result), 2)
        self.assertEqual([x['entries'][0]['iat_rva'] for x in result],
                         [0x2170, 0x2190])

    def test_missing_terminator_rejected(self):
        data = bytearray(fixture())
        struct.pack_into('<I', data, 0x520, 1)
        with self.assertRaises(ValueError):
            parse_delay_imports(data)

    def test_unmapped_thunk_rejected(self):
        data = bytearray(fixture())
        struct.pack_into('<I', data, 0x560, 0x2fff)
        with self.assertRaises(ValueError):
            parse_delay_imports(data)

    def test_invalid_va_rejected(self):
        data = bytearray(fixture(va=True))
        struct.pack_into('<I', data, 0x504, 0x2140)
        with self.assertRaisesRegex(ValueError, 'below image base'):
            parse_delay_imports(data)

    def test_missing_name_terminator_rejected(self):
        data = bytearray(fixture())
        data[0x540:0x600] = b'X' * 0xc0
        with self.assertRaises(ValueError):
            parse_delay_imports(data)

    def test_half_populated_directory_rejected(self):
        data = bytearray(fixture())
        struct.pack_into('<I', data, 0x98 + 96 + 13 * 8 + 4, 0)
        with self.assertRaisesRegex(ValueError, 'Half-populated'):
            parse_delay_imports(data)

    def test_bad_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            analyze(fixture(), '0' * 64)

    def test_no_delay_directory(self):
        data = sample_pe()
        result, _ = analyze(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(result['delay_descriptors'], 0)

    def test_output_separation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, public, private = (root / name for name in ('sample.exe', 'public.json', 'private.json'))
            source.write_bytes(fixture())
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            run(source, digest, public, private)
            self.assertNotIn('DELAYTEST', public.read_text(encoding='utf-8'))
            self.assertIn('DELAYTEST', private.read_text(encoding='utf-8'))
            with self.assertRaisesRegex(ValueError, 'must differ'):
                run(source, digest, source, private)
            with self.assertRaisesRegex(ValueError, 'must differ'):
                run(source, digest, public, public)


if __name__ == '__main__':
    unittest.main()
