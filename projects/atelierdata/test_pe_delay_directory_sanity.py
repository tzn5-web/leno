"""Synthetic PE32 regression fixtures; no proprietary data used."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from pe_delay_directory_sanity import analyze, analyze_zip, run, ORIGINAL_MEMBER


def fixture(delay=b'', rva=0x1000, declared=None):
    blob = bytearray(0x800)
    blob[:2] = b'MZ'
    struct.pack_into('<I', blob, 0x3c, 0x80)
    blob[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', blob, 0x84, 0x14c, 1, 0, 0, 0, 224, 0x102)
    o = 0x98
    struct.pack_into('<H', blob, o, 0x10b)
    struct.pack_into('<I', blob, o + 28, 0x400000)
    struct.pack_into('<I', blob, o + 60, 0x200)
    struct.pack_into('<I', blob, o + 92, 16)
    struct.pack_into('<II', blob, o + 96 + 13 * 8, rva if delay else 0,
                     len(delay) if declared is None else declared)
    s = o + 224
    blob[s:s + 8] = b'.rdata\0\0'
    struct.pack_into('<IIII', blob, s + 8, 0x600, 0x1000, 0x600, 0x200)
    blob[0x200:0x200 + len(delay)] = delay
    blob[0x300:0x30b] = b'EXAMPLE.dll\0'
    data = bytes(blob)
    return data, hashlib.sha256(data).hexdigest()


class DelayDirectorySanityTests(unittest.TestCase):
    def test_absent(self):
        data, sha = fixture()
        self.assertEqual(analyze(data, sha)['state'], 'ABSENT')

    def test_valid_rva_descriptor(self):
        row = struct.pack('<8I', 1, 0x1100, 0, 0x1200, 0x1300, 0, 0, 0)
        data, sha = fixture(row + bytes(32))
        result = analyze(data, sha)
        self.assertEqual(result['state'], 'STRUCTURALLY_PLAUSIBLE')
        self.assertEqual(result['plausible_name_descriptors'], 1)
        self.assertTrue(result['zero_terminator_found'])

    def test_valid_va_descriptor(self):
        row = struct.pack('<8I', 0, 0x401100, 0, 0x401200, 0x401300, 0, 0, 0)
        data, sha = fixture(row + bytes(32))
        self.assertEqual(analyze(data, sha)['plausible_name_descriptors'], 1)

    def test_random_like_invalid_flags(self):
        row = struct.pack('<8I', 0xdeadbeef, 0xffffffff, 1, 2, 3, 4, 5, 6)
        data, sha = fixture(row * 2)
        result = analyze(data, sha)
        self.assertEqual(result['invalid_attribute_slots'], 2)
        self.assertIn('MISSING_ZERO_TERMINATOR', result['issues'])
        self.assertEqual(result['state'], 'NOT_VALIDATED_AS_STANDARD_DELAY_IMPORTS')

    def test_partial_trailing_bytes(self):
        data, sha = fixture(bytes(32) + b'123')
        self.assertIn('NON_DESCRIPTOR_TRAILING_BYTES', analyze(data, sha)['issues'])

    def test_sha256_required(self):
        data, sha = fixture()
        with self.assertRaises(ValueError):
            analyze(data, '0' * 64)

    def test_unmapped_directory(self):
        data, sha = fixture(bytes(64), rva=0x800000)
        self.assertIn('UNMAPPED_DIRECTORY', analyze(data, sha)['issues'])

    def test_blocked_package_refused(self):
        with self.assertRaises(ValueError):
            analyze_zip(Path('autodata_part_0016.zip'), '0' * 64)

    def test_zip_integration_and_no_binary_export(self):
        data, sha = fixture()
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            z = folder / 'autodata_part_0001.zip'
            with zipfile.ZipFile(z, 'w') as stream:
                stream.writestr(ORIGINAL_MEMBER, data)
            out = folder / 'report.json'
            result = run(z, sha, out)
            self.assertEqual(result['state'], 'ABSENT')
            self.assertNotIn('EXAMPLE.dll', out.read_text())
            with self.assertRaises(ValueError):
                run(z, sha, z)


if __name__ == '__main__':
    unittest.main()
