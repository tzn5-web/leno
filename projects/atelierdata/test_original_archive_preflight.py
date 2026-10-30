"""Synthetic-only tests; no original Autodata data, executable or keys."""
import hashlib
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from original_archive_preflight import audit, inspect_pe, load_manifest


def fake_pe():
    b = bytearray(0x600)
    b[:2] = b'MZ'
    struct.pack_into('<I', b, 0x3c, 0x80)
    b[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', b, 0x84, 0x14c, 1)
    struct.pack_into('<H', b, 0x94, 0xe0)
    opt = 0x98
    struct.pack_into('<H', b, opt, 0x10b)
    struct.pack_into('<H', b, opt + 68, 2)
    struct.pack_into('<II', b, opt + 96 + 8, 0x1000, 40)
    sec = opt + 0xe0
    struct.pack_into('<IIII', b, sec + 8, 0x300, 0x1000, 0x300, 0x200)
    struct.pack_into('<I', b, 0x200 + 12, 0x1050)
    b[0x250:0x250 + 13] = b'KERNEL32.dll\0'
    b[0x300:0x300 + 16] = b'SentinelKeyW.DLL'
    return bytes(b)


class OriginalArchivePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.exe = fake_pe()
        self.first = b'FIRST'
        self.second = b'SECOND'
        self.zip1 = self.root / 'autodata_part_0001.zip'
        self.zip2 = self.root / 'autodata_part_0002.zip'
        self.exe_name = 'Autodata__3.45/ADCDA2/ADBCD.exe'
        self.idf_name = 'Autodata__3.45/ADCDA2/COMMON/TEST.IDF'
        self.manifest = {'package_count': 2, 'files': [
            {'path': self.exe_name, 'size_bytes': len(self.exe), 'chunks': [self.chunk(1, self.exe_name, self.exe)]},
            {'path': self.idf_name, 'size_bytes': len(self.first) + len(self.second), 'chunks': [
                self.chunk(1, self.idf_name + '.chunk0000', self.first),
                self.chunk(2, self.idf_name + '.chunk0001', self.second)]}]}
        self.manifest_path = self.root / 'manifest.json'
        self.write_manifest()
        with zipfile.ZipFile(self.zip1, 'w') as z:
            z.writestr(self.exe_name, self.exe)
            z.writestr(self.idf_name + '.chunk0000', self.first)
        with zipfile.ZipFile(self.zip2, 'w') as z:
            z.writestr(self.idf_name + '.chunk0001', self.second)

    def chunk(self, n, entry, data):
        return {'package': f'autodata_part_{n:04}.zip', 'entry': entry,
                'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding='utf-8')

    def test_full_integrity_and_pe_imports(self):
        result = audit(self.manifest_path, self.root)
        self.assertTrue(result['complete_archive'])
        self.assertEqual(result['verified_chunk_count'], 3)
        self.assertEqual(result['verified_idf_file_count'], 1)
        self.assertEqual(result['pe']['imported_dlls'], ['KERNEL32.dll'])
        self.assertTrue(result['pe']['sentinel_dll_literal_present'])
        self.assertFalse(result['license_verified'])

    def test_missing_second_chunk_does_not_pass_idf(self):
        self.zip2.unlink()
        result = audit(self.manifest_path, self.root)
        self.assertEqual(result['verified_chunk_count'], 2)
        self.assertEqual(result['verified_idf_file_count'], 0)
        self.assertEqual(result['data_integrity'], 'INCOMPLETE')
        self.assertEqual(result['missing_packages'], ['autodata_part_0002.zip'])

    def test_tampered_chunk_rejected(self):
        with zipfile.ZipFile(self.zip2, 'w') as z:
            z.writestr(self.idf_name + '.chunk0001', b'CHANGE')
        result = audit(self.manifest_path, self.root)
        self.assertEqual(result['verified_idf_file_count'], 0)
        self.assertTrue(result['errors'])

    def test_manifest_traversal_rejected(self):
        self.manifest['files'][0]['path'] = 'Autodata__3.45/../bad'
        self.write_manifest()
        with self.assertRaises(ValueError):
            load_manifest(self.manifest_path)

    def test_invalid_pe_rejected(self):
        with self.assertRaises(ValueError):
            inspect_pe(b'MZ' + bytes(300))


if __name__ == '__main__':
    unittest.main()
