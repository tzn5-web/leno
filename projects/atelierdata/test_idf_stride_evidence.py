"""Only synthetic fixtures. No original proprietary bytes."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from idf_stride_evidence import analyze, strongest_stride, main


def manifest_and_parts(root, rows):
    files = []
    for i, (name, data) in enumerate(rows, 1):
        package = f'autodata_part_{i:04d}.zip'
        entry = f'Fake/{name}'
        with zipfile.ZipFile(root / package, 'w') as z:
            z.writestr(entry, data)
        files.append(dict(path=entry, size_bytes=len(data), chunks=[dict(
            package=package, entry=entry, bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest())]))
    return dict(files=files)


class IDFStrideTests(unittest.TestCase):
    def test_fixed_stride_detection(self):
        marker = b'ABCDEFGH'
        payload = b'x' * 100 + (marker + b'0' * 13) * 30
        run = strongest_stride(payload)
        self.assertEqual(run['count'], 30)
        self.assertEqual(run['stride'], 21)
        self.assertEqual(run['start'], 100)

    def test_19_byte_stride(self):
        run = strongest_stride((b'abcdefgh' + b'z' * 11) * 12)
        self.assertEqual((run['count'], run['stride']), (12, 19))

    def test_cross_file_private_token_not_exported(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            shared = b'ABCDEFGH'
            manifest = manifest_and_parts(root, [
                ('SGOPS.IDF', (shared + b'a' * 13) * 25),
                ('SGINT.IDF', (shared + b'b' * 13) * 25),
                ('FAS.IDF', (b'ZXYABCDE' + b'c' * 11) * 20)])
            result = analyze(manifest, root)
            self.assertTrue(result['sgops_sgint_same_dominant_token'])
            self.assertEqual(result['analyzed_files'], 3)
            self.assertNotIn('ABCDEFGH', str(result))
            self.assertFalse(result['idf_decoder_proven'])

    def test_sha256_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = manifest_and_parts(root, [('FAS.IDF', b'synthetic')])
            manifest['files'][0]['chunks'][0]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                analyze(manifest, root, ('FAS.IDF',))

    def test_duplicate_zip_member_rejected_even_when_last_hash_matches(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            payload = b'synthetic-original'
            manifest = manifest_and_parts(root, [('FAS.IDF', payload)])
            archive_path = root / 'autodata_part_0001.zip'
            # ZIP allows duplicate names; getinfo() normally selects the last.
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(archive_path, 'a') as archive:
                    archive.writestr('Fake/FAS.IDF', payload)
            with self.assertRaisesRegex(ValueError, 'ambiguous'):
                analyze(manifest, root, ('FAS.IDF',))

    def test_zip_symlink_refused_before_open(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = manifest_and_parts(root, [('FAS.IDF', b'synthetic')])
            original = root / 'autodata_part_0001.zip'
            target = root / 'archive-target.zip'
            original.rename(target)
            try:
                original.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest('Symlink creation not available on this runner')
            with self.assertRaisesRegex(ValueError, 'Symlink ZIP refused'):
                analyze(manifest, root, ('FAS.IDF',))

    def test_zip_source_replaced_with_symlink_at_open_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = manifest_and_parts(root, [('FAS.IDF', b'synthetic')])
            original = root / 'autodata_part_0001.zip'
            target = root / 'archive-target.zip'
            original.rename(target)
            real_open = __import__('os').open
            def swap_at_open(path, flags, *args, **kwargs):
                if Path(path) == original:
                    try:
                        original.symlink_to(target)
                    except (OSError, NotImplementedError):
                        raise unittest.SkipTest('Symlink creation not available')
                return real_open(path, flags, *args, **kwargs)
            with patch('idf_stride_evidence.os.open', side_effect=swap_at_open):
                with self.assertRaises((ValueError, OSError)):
                    analyze(manifest, root, ('FAS.IDF',))

    def test_missing_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = manifest_and_parts(root, [('FAS.IDF', b'synthetic')])
            (root / 'autodata_part_0001.zip').unlink()
            with self.assertRaises(FileNotFoundError):
                analyze(manifest, root, ('FAS.IDF',))

    def test_blocked_part_0016_is_rejected_before_open(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = manifest_and_parts(root, [('FAS.IDF', b'synthetic')])
            manifest['files'][0]['chunks'][0]['package'] = 'autodata_part_0016.zip'
            with patch('idf_stride_evidence.zipfile.ZipFile',
                       side_effect=AssertionError('Blocked ZIP must never be opened')) as opener:
                with self.assertRaisesRegex(ValueError, 'Blocked package part_0016'):
                    analyze(manifest, root, ('FAS.IDF',))
                opener.assert_not_called()

    def test_existing_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / 'inventory.json'
            manifest.write_text(json.dumps({'files': []}), encoding='utf-8')
            report = root / 'evidence.json'
            report.write_text('SENTINEL', encoding='utf-8')
            argv = ['idf_stride_evidence.py', '--manifest', str(manifest),
                    '--parts-dir', str(root), '--output', str(report)]
            with patch.object(sys, 'argv', argv), patch('idf_stride_evidence.analyze', return_value={'idf_decoder_proven': False}):
                with self.assertRaises(FileExistsError):
                    main()
            self.assertEqual(report.read_text(encoding='utf-8'), 'SENTINEL')

    def test_new_report_created(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / 'inventory.json'
            manifest.write_text(json.dumps({'files': []}), encoding='utf-8')
            report = root / 'evidence.json'
            argv = ['idf_stride_evidence.py', '--manifest', str(manifest),
                    '--parts-dir', str(root), '--output', str(report)]
            with patch.object(sys, 'argv', argv), patch('idf_stride_evidence.analyze', return_value={'idf_decoder_proven': False}):
                main()
            self.assertFalse(json.loads(report.read_text(encoding='utf-8'))['idf_decoder_proven'])

    def test_no_repetition(self):
        self.assertIsNone(strongest_stride(b'123456789'))
        self.assertIsNone(strongest_stride(b'0' * 1000))


if __name__ == '__main__':
    unittest.main()
