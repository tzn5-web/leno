"""Synthetic regression tests: never require or read proprietary files."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from idf_zip_entropy_clusters import audit


class ZipEntropyClusterTests(unittest.TestCase):
    def make_zip(self, folder, entries, name='allowed_part_0001.zip'):
        path = Path(folder) / name
        with zipfile.ZipFile(path, 'w') as archive:
            for entry, content in entries:
                archive.writestr(entry, content)
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_matching_prefix_and_aggregate_redaction(self):
        with tempfile.TemporaryDirectory() as folder:
            entries = [('PRIVATE/A.IDF', b'Q' * 20 + b'A' * 4096),
                       ('PRIVATE/B.IDF', b'Q' * 20 + b'B' * 4096),
                       ('PRIVATE/C.IDF', b'R' * 4096)]
            path, digest = self.make_zip(folder, entries)
            result = audit(path, digest)
            self.assertEqual(result['idf_files_checked'], 3)
            self.assertEqual(result['shared_first16_prefix_pairs'], 1)
            self.assertEqual(result['longest_shared_prefix_bytes_within_first64'], 20)
            self.assertFalse(result['idf_decoder_proven'])
            self.assertNotIn('PRIVATE', str(result))
            self.assertNotIn(digest, str(result))

    def test_wrong_archive_hash_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path, _ = self.make_zip(folder, [('X.IDF', b'x')])
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                audit(path, '0' * 64)

    def test_blocked_archive_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'autodata_part_0016.zip'
            with self.assertRaisesRegex(ValueError, 'Blocked'):
                audit(path, '0' * 64)

    def test_unsafe_zip_member_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path, digest = self.make_zip(folder, [('../PRIVATE.IDF', b'private')])
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                audit(path, digest)

    def test_duplicate_casefold_member_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path, digest = self.make_zip(folder, [('A.IDF', b'first'), ('a.idf', b'second')])
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                audit(path, digest)

    def test_truncated_or_tampered_zip_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path, digest = self.make_zip(folder, [('A.IDF', b'content')])
            path.write_bytes(path.read_bytes()[:-5])
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                audit(path, digest)


if __name__ == '__main__':
    unittest.main()
