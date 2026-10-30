"""Synthetic-only tests: no proprietary binaries, keys or Autodata content."""
import hashlib
import json
import struct
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from original_runtime_dependency_audit import audit

ROOT = 'Autodata__3.45/ADCDA2/'

def pe_bytes(machine=0x14c, imported='KERNEL32.dll', sentinel=False):
    buf = bytearray(0x600)
    buf[:2] = b'MZ'
    struct.pack_into('<I', buf, 0x3c, 0x80)
    buf[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', buf, 0x84, machine, 1)
    struct.pack_into('<H', buf, 0x94, 0xe0)
    opt = 0x98
    struct.pack_into('<H', buf, opt, 0x10b)
    struct.pack_into('<H', buf, opt + 68, 2)
    struct.pack_into('<II', buf, opt + 96 + 8, 0x1000, 40)
    sec = opt + 0xe0
    struct.pack_into('<IIII', buf, sec + 8, 0x300, 0x1000, 0x300, 0x200)
    struct.pack_into('<I', buf, 0x200 + 12, 0x1050)
    name = imported.encode('ascii') + b'\0'
    buf[0x250:0x250 + len(name)] = name
    if sentinel:
        buf[0x300:0x310] = b'SentinelKeyW.DLL'
    return bytes(buf)

class DependencyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.exe = pe_bytes(imported='ChilkatUtil.dll', sentinel=True)
        self.dll = pe_bytes(imported='KERNEL32.dll')
        self.files = [
            self.item('ADBCD.exe', self.exe, 1),
            self.item('ChilkatUtil.dll', self.dll, 2),
            self.item('SentinelKeyW.DLL', b'NOT_DOWNLOADED', 3),
        ]
        self.write()

    def item(self, name, data, part):
        path = ROOT + name
        return {'path': path, 'size_bytes': len(data), 'chunks': [
            {'package': f'autodata_part_{part:04d}.zip', 'entry': path,
             'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}]}

    def write(self):
        (self.root/'INVENTAR.json').write_text(json.dumps(
            {'files': self.files, 'package_count': 3}), encoding='utf-8')
        for i, (name, data) in enumerate((('ADBCD.exe', self.exe),
                                           ('ChilkatUtil.dll', self.dll)), 1):
            with zipfile.ZipFile(self.root/f'autodata_part_{i:04d}.zip', 'w') as z:
                z.writestr(ROOT + name, data)

    def run_audit(self):
        return audit(self.root/'INVENTAR.json', self.root)

    def test_verified_closure_and_unavailable_literal(self):
        result = self.run_audit()
        self.assertEqual(result['verified_component_count'], 2)
        self.assertEqual(result['unavailable_component_count'], 1)
        self.assertTrue(result['sentinel_literal_candidate'])
        self.assertEqual(result['root_shipped_dll_name_literals'],
                         ['CHILKATUTIL.DLL', 'SENTINELKEYW.DLL'])
        self.assertFalse(result['sentinel_available_and_verified'])
        self.assertEqual(result['unresolved_direct_imports'], [])
        self.assertEqual([x['classification'] for x in result['reachable_direct_imports']],
                         ['packaged_verified_matching_architecture', 'windows_system_candidate'])
        self.assertFalse(result['windows_runtime_tested'])

    def test_missing_direct_import_distinguished_from_literal(self):
        self.exe = pe_bytes(imported='SentinelKeyW.DLL', sentinel=True)
        self.files[0] = self.item('ADBCD.exe', self.exe, 1)
        self.write()
        result = self.run_audit()
        self.assertEqual(result['unresolved_direct_imports'][0]['classification'],
                         'packaged_but_unavailable_or_unverified')

    def test_wrong_architecture_detected(self):
        self.dll = pe_bytes(machine=0x8664)
        self.files[1] = self.item('ChilkatUtil.dll', self.dll, 2)
        self.write()
        result = self.run_audit()
        self.assertEqual(result['unresolved_direct_imports'][0]['classification'],
                         'packaged_architecture_mismatch')

    def test_tampered_dll_rejected_without_execution(self):
        self.dll = pe_bytes(imported='USER32.dll')
        self.write()  # manifest intentionally retains original digest
        result = self.run_audit()
        self.assertEqual(result['components']['CHILKATUTIL.DLL']['status'], 'sha256_mismatch')
        self.assertEqual(result['unresolved_direct_imports'][0]['classification'],
                         'packaged_but_unavailable_or_unverified')

    def test_duplicate_zip_member_rejected(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.root/'autodata_part_0002.zip', 'a') as z:
                z.writestr(ROOT+'ChilkatUtil.dll', self.dll)
        result = self.run_audit()
        self.assertEqual(result['components']['CHILKATUTIL.DLL']['status'], 'duplicate_zip_member')

    def test_manifest_path_traversal_rejected(self):
        self.files[0]['path'] = ROOT + '../evil.exe'
        self.write()
        with self.assertRaises(ValueError):
            self.run_audit()

if __name__ == '__main__':
    unittest.main()
