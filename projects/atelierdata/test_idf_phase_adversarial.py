"""Regression tests for phase statistics under adversarial synthetic data.

No original IDF content is used. Phase concentration is descriptive only.
"""
import unittest
from idf_stride_hypotheses import compare_stride_hypotheses


class PhaseAdversarialTests(unittest.TestCase):
    def test_phase_fraction_is_bounded(self):
        for sample in (b"", b"A" * 1024, bytes(range(19)) * 80,
                       b"".join(b"ABCDEFGH" + bytes([i]) * 11 for i in range(80))):
            report = compare_stride_hypotheses(sample)
            for stride, item in report["hypotheses"].items():
                self.assertGreaterEqual(item["dominant_phase_fraction"], 0)
                self.assertLessEqual(item["dominant_phase_fraction"], 1)
                self.assertLessEqual(item["dominant_phase_match_count"],
                                     item["matching_window_pairs"])
                self.assertFalse(report["idf_decoder_proven"])

    def test_phase_concentration_is_not_boundary_proof(self):
        # Fixed-period synthetic data is concentrated by construction,
        # but every sliding window is equal at that period.
        report = compare_stride_hypotheses(bytes(range(19)) * 80)
        self.assertTrue(report["hypotheses"]["19"]["global_periodicity_confounder"])
        self.assertFalse(report["idf_decoder_proven"])

    def test_no_matches_has_zero_fraction(self):
        report = compare_stride_hypotheses(bytes(range(64)))
        for item in report["hypotheses"].values():
            self.assertEqual(item["matching_window_pairs"], 0)
            self.assertEqual(item["dominant_phase_fraction"], 0)

    def test_invalid_stride_rejected(self):
        for stride in (8, 129, 19.0, False):
            with self.subTest(stride=stride):
                with self.assertRaises(ValueError):
                    compare_stride_hypotheses(b"test", (stride,))


if __name__ == "__main__":
    unittest.main()
