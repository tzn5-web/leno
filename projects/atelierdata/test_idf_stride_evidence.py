"""Only synthetic fixtures. No original proprietary bytes."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from idf_stride_evidence import analyze, strongest_stride


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

    def test_missing_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = manifest_and_parts(root, [('FAS.IDF', b'synthetic')])
            (root / 'autodata_part_0001.zip').unlink()
            with self.assertRaises(FileNotFoundError):
                analyze(manifest, root, ('FAS.IDF',))

    def test_no_repetition(self):
        self.assertIsNone(strongest_stride(b'123456789'))
        self.assertIsNone(strongest_stride(b'0' * 1000))


if __name__ == '__main__':
    unittest.main()
