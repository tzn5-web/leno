"""Synthetic-only regression for complete-file, phase-aligned IDF heuristics."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from idf_full_phase import phase_summary
from idf_zip_full_phase_audit import audit_full


def varied(stride, rows, token=b'ABCD1234'):
    return b''.join(token + bytes([i % 251, (i * 7) % 251]) +
                    b'X' * (stride - 10) for i in range(rows))


class FullPhaseTests(unittest.TestCase):
    def test_complete_rows_and_variable_suffix_required(self):
        self.assertEqual(phase_summary(varied(19, 64), 19)['longest_qualified_run'], 64)
        self.assertEqual(phase_summary(varied(19, 31) + b'ABCD1234', 19)['qualified_runs'], 0)
        self.assertEqual(phase_summary((b'ABCD1234' + b'X' * 11) * 64, 19)['qualified_runs'], 0)
        self.assertEqual(phase_summary(b'\x00' * 4096, 19)['qualified_runs'], 0)

    def test_accelerated_and_stdlib_paths_agree(self):
        for stride in (17, 19, 21):
            sample = b'head' + varied(stride, 64) + b'tail'
            fast = phase_summary(sample, stride)
            with patch('idf_full_phase._np', None):
                slow = phase_summary(sample, stride)
            self.assertEqual(fast, slow)

    def test_one_phase_and_no_overlapping_double_count(self):
        data = b'padding' + varied(21, 64) + b'gap' + varied(21, 48, b'WXYZ9876')
        result = phase_summary(data, 21)
        self.assertEqual(result['qualified_runs'], 2)
        self.assertEqual(result['longest_qualified_run'], 64)
        self.assertEqual(result['qualified_coverage_bytes'], 112 * 21)
        self.assertEqual(result['distinct_phases'], 2)

    def test_full_zip_finds_late_only_and_keeps_private_bytes_out(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'allowed_part_0001.zip'
            # Late evidence appears only after the first 2 MiB.
            late = b'\x00' * (2 * 1024 * 1024 + 19) + varied(19, 64)
            with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('PRIVATE.IDF', late)
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            result = audit_full(path, expected)
            self.assertEqual(result['by_stride']['19']['files_qualified'], 1)
            self.assertEqual(result['by_stride']['19']['new_files_after_first_window'], 1)
            self.assertEqual(result['by_stride']['19']['files_single_phase'], 1)
            self.assertFalse(result['idf_decoder_proven'])
            self.assertNotIn('PRIVATE', str(result))

    def test_wrong_sha_and_blocked_part_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'autodata_part_0016.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('A.IDF', varied(19, 64))
            with self.assertRaisesRegex(ValueError, 'Blocked'):
                audit_full(path, '0' * 64)
            path.rename(Path(d) / 'allowed_part_0001.zip')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                audit_full(Path(d) / 'allowed_part_0001.zip', '0' * 64)


if __name__ == '__main__':
    unittest.main()
