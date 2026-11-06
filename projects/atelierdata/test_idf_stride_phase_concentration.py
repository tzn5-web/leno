"""Synthetic-only checks for aggregate stride phase evidence."""
import unittest
from idf_stride_hypotheses import compare_stride_hypotheses


class PhaseConcentrationTests(unittest.TestCase):
    def test_single_phase_repeated_marker(self):
        stride = 19
        block = b"ABCDEFGH" + bytes(range(11))
        sample = block * 100
        row = compare_stride_hypotheses(sample, (stride,))["hypotheses"][str(stride)]
        self.assertGreater(row["dominant_phase_match_count"], 0)
        self.assertGreater(row["dominant_phase_fraction"], 0.0)
        self.assertLessEqual(row["dominant_phase_fraction"], 1.0)

    def test_constant_buffer_is_flagged(self):
        row = compare_stride_hypotheses(b"Z" * 400, (21,))["hypotheses"]["21"]
        self.assertTrue(row["global_periodicity_confounder"])
        self.assertLess(row["dominant_phase_fraction"], 0.1)

    def test_empty_buffer_has_zero_fraction(self):
        row = compare_stride_hypotheses(b"", (19,))["hypotheses"]["19"]
        self.assertEqual(row["dominant_phase_match_count"], 0)
        self.assertEqual(row["dominant_phase_fraction"], 0.0)


if __name__ == "__main__":
    unittest.main()
