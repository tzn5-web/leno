"""Synthetic-only tests for private IDF prefix and SHA256 audit."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from original_idf_prefix_provenance import audit, main

ROOT = 'Autodata__3.45/ADCDA2/COMMON/'
PART = 'autodata_part_0001.zip'
BLOCKED = 'autodata_part_0016.zip'


class PrefixProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = {'FIRST.IDF': b'ABCDEFGHIJKLMNOPQRST' + b'x' * 400,
                     'SECOND.IDF': b'ABCDEFGHIJKLMNOPQRST' + b'y' * 400,
                     'THIRD.IDF': b'ZZZZ' + b'z' * 400}
        self.write()

    def write(self):
        files = []
        with zipfile.ZipFile(self.root / PART, 'w') as z:
            for name, data in self.data.items():
                entry = ROOT + name
                z.writestr(entry, data)
                files.append({'path': entry, 'size_bytes': len(data), 'chunks': [
                    {'package': PART, 'entry': entry, 'bytes': len(data),
                     'sha256': hashlib.sha256(data).hexdigest()}]})
        (self.root / 'INVENTAR.json').write_text(json.dumps(
            {'files': files, 'package_count': 1}), encoding='utf-8')

    def run_audit(self):
        return audit(self.root / 'INVENTAR.json', self.root, [PART])

    def test_verified_prefixes_and_public_privacy(self):
        result = self.run_audit()
        self.assertEqual(result['single_chunk_idf_sha256_verified'], 3)
        self.assertEqual(result['compared_pairs'], 3)
        self.assertEqual(result['shared_prefix_pairs_at_least_bytes']['20'], 1)
        self.assertEqual(result['shared_prefix_pairs_at_least_bytes']['32'], 0)
        self.assertEqual(result['longest_shared_sample_prefix_bytes'], 20)
        self.assertFalse(result['idf_decoded'])
        public = json.dumps(result)
        self.assertNotIn('FIRST.IDF', public)
        self.assertNotIn('ABCDEFGHIJKLMNOPQRST', public)
        self.assertNotIn('header_hex', public)

    def test_tampering_rejected(self):
        self.data['SECOND.IDF'] += b'corruption'
        with zipfile.ZipFile(self.root / PART, 'w') as z:
            for name, data in self.data.items():
                z.writestr(ROOT + name, data)
        with self.assertRaisesRegex(ValueError, 'SHA256|size|mismatched'):
            self.run_audit()

    def test_duplicate_entry_rejected(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.root / PART, 'a') as z:
                z.writestr(ROOT + 'FIRST.IDF', self.data['FIRST.IDF'])
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            self.run_audit()

    def test_blocked_part_never_probed(self):
        with patch.object(Path, 'is_file', side_effect=AssertionError('filesystem probe')):
            with self.assertRaisesRegex(ValueError, 'Blocked'):
                audit(self.root / 'INVENTAR.json', self.root, [BLOCKED])

    def test_reject_unknown_and_duplicate_package(self):
        for selection in ([PART, PART], ['autodata_part_0002.zip']):
            with self.assertRaises(ValueError):
                audit(self.root / 'INVENTAR.json', self.root, selection)

    def test_missing_package_rejected(self):
        (self.root / PART).unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.run_audit()

    def test_symlink_package_rejected(self):
        original = self.root / PART
        original.rename(self.root / 'real.zip')
        try:
            original.symlink_to(self.root / 'real.zip')
        except (OSError, NotImplementedError):
            self.skipTest('Symlink unavailable')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.run_audit()

    def test_no_idf_in_package(self):
        self.data = {}
        self.write()
        # The selected package exists in the manifest but has no IDF members.
        path = self.root / 'INVENTAR.json'
        entry = ROOT + 'README.TXT'
        data = b'authorized synthetic text'
        path.write_text(json.dumps({'files': [{'path': entry, 'size_bytes': len(data),
            'chunks': [{'package': PART, 'entry': entry, 'bytes': len(data),
                        'sha256': hashlib.sha256(data).hexdigest()}]}],
            'package_count': 1}), encoding='utf-8')
        with zipfile.ZipFile(self.root / PART, 'w') as z:
            z.writestr(entry, data)
        with self.assertRaisesRegex(ValueError, 'No complete'):
            self.run_audit()

    def test_cli_error_sanitized(self):
        with patch('sys.argv', ['audit', '--manifest', str(self.root / 'INVENTAR.json'),
                                '--parts-dir', str(self.root), '--package', BLOCKED]):
            self.assertEqual(main(), 2)


if __name__ == '__main__':
    unittest.main()
