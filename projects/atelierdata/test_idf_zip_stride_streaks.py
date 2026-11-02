"""Synthetic-only regression tests: no proprietary samples."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from idf_zip_stride_streaks import audit, longest_streak


class StrideStreakTests(unittest.TestCase):
    def make_zip(self, folder, entries, name='allowed_part_0001.zip'):
        path = Path(folder) / name
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, content in entries:
                z.writestr(name, content)
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_detects_19_and_21_without_claiming_decoder(self):
        with tempfile.TemporaryDirectory() as d:
            token = b'ABCD1234'
            a = (token + b'x' * 11) * 64
            b = (token + b'y' * 13) * 64
            p, h = self.make_zip(d, [('A.IDF', a), ('B.IDF', b)])
            result = audit(p, h)
            self.assertEqual(result['idf_files_crc_checked'], 2)
            self.assertEqual(result['files_with_32_diverse_repeated_tokens_by_stride']['19'], 1)
            self.assertEqual(result['files_with_32_diverse_repeated_tokens_by_stride']['21'], 1)
            self.assertFalse(result['idf_decoder_proven'])
            self.assertNotIn('A.IDF', str(result))

    def test_repetitive_zero_not_diverse(self):
        longest, diverse = longest_streak(b'\x00' * 4096, 21)
        self.assertGreater(longest, 32)
        self.assertEqual(diverse, 0)

    def test_wrong_sha_and_blocked_part(self):
        with tempfile.TemporaryDirectory() as d:
            p, _ = self.make_zip(d, [('A.IDF', b'abc')])
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                audit(p, '0' * 64)
            p, _ = self.make_zip(d, [('A.IDF', b'abc')], 'autodata_part_0016.zip')
            with self.assertRaisesRegex(ValueError, 'Blocked'):
                audit(p, '0' * 64)

    def test_path_traversal_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p, h = self.make_zip(d, [('../secret.IDF', b'abc')])
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                audit(p, h)
            p, h = self.make_zip(d, [('A.IDF', b'1'), ('a.idf', b'2')])
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                audit(p, h)

    def test_short_and_randomish_samples_not_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p, h = self.make_zip(d, [('X.IDF', bytes(range(256)) * 8), ('Y.IDF', b'abc')])
            result = audit(p, h)
            self.assertEqual(result['files_with_32_diverse_repeated_tokens_by_stride'],
                             {'17': 0, '19': 0, '21': 0})


if __name__ == '__main__':
    unittest.main()
