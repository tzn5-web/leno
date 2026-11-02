"""Synthetic-only regressions for bounded-memory full-phase matching."""
import unittest
from unittest.mock import patch
from idf_full_phase import phase_summary, MATCH_CHUNK


def rows(stride, count, token=b'ABCD1234'):
    return b''.join(token + bytes((i % 251, (i * 7) % 251)) +
                    b'X' * (stride - 10) for i in range(count))


class BoundedFullPhaseTests(unittest.TestCase):
    def test_chain_crosses_numpy_chunk_boundary(self):
        start = MATCH_CHUNK - 19 * 20 + 3
        data = b'\0' * start + rows(19, 96) + b'\0' * 25
        expected = {'qualified_runs': 1, 'longest_qualified_run': 96,
                    'distinct_phases': 1, 'qualified_coverage_bytes': 96 * 19}
        self.assertEqual(phase_summary(data, 19), expected)
        with patch('idf_full_phase._np', None):
            self.assertEqual(phase_summary(data, 19), expected)

    def test_no_false_evidence_from_large_low_entropy_input(self):
        data = b'\0' * (MATCH_CHUNK * 3 + 97)
        self.assertEqual(phase_summary(data, 21)['qualified_runs'], 0)
        with patch('idf_full_phase._np', None):
            self.assertEqual(phase_summary(data, 21)['qualified_runs'], 0)

    def test_complete_row_and_saturation(self):
        data = rows(17, 65550)
        for mode in (True, False):
            with patch('idf_full_phase._np', None if not mode else __import__('numpy')):
                result = phase_summary(data, 17)
                self.assertEqual(result['longest_qualified_run'], 65535)
                self.assertEqual(result['qualified_coverage_bytes'], 65535 * 17)

    def test_small_randomized_agreement(self):
        import random
        rng = random.Random(42)
        for stride in (17, 19, 21):
            for _ in range(4):
                data = rng.randbytes(23) + rows(stride, 45) + rng.randbytes(35)
                expected = phase_summary(data, stride)
                with patch('idf_full_phase._np', None):
                    self.assertEqual(phase_summary(data, stride), expected)


if __name__ == '__main__':
    unittest.main()
