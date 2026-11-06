"""Regression tests for byte-disjoint stride evidence thresholds (synthetic only)."""
import unittest
from unittest.mock import patch
from idf_stride_negative_controls import rank_stride_evidence


def fake_compare(sample, strides):
    rows = {}
    for stride in strides:
        denom = 700 if stride == 21 else 700
        rows[str(stride)] = {
            "possible_window_pairs": denom,
            "matching_window_pairs": 350 if stride == 21 else 70,
            "low_diversity_confounder": False,
            "global_periodicity_confounder": False,
            "qualified_runs": 1,
        }
    return {"hypotheses": rows}


class DisjointEvidenceTests(unittest.TestCase):
    @patch("idf_stride_negative_controls.compare_stride_hypotheses", side_effect=fake_compare)
    def test_overlapping_count_does_not_clear_threshold(self, _):
        row = rank_stride_evidence(b"x" * 800, (21,))["results"][0]
        self.assertEqual(row["nonoverlapping_pair_upper_bound"], 87)
        self.assertEqual(row["disjoint_span_pair_count"], 24)
        self.assertTrue(row["insufficient_pairs"])
        self.assertTrue(row["inconclusive"])

    @patch("idf_stride_negative_controls.compare_stride_hypotheses")
    def test_disjoint_threshold(self, mocked):
        def compare(sample, strides):
            rows = {}
            for stride in strides:
                rows[str(stride)] = {
                    "possible_window_pairs": 1000,
                    "matching_window_pairs": 500 if stride == 21 else 100,
                    "low_diversity_confounder": False,
                    "global_periodicity_confounder": False,
                    "qualified_runs": 1,
                }
            return {"hypotheses": rows}
        mocked.side_effect = compare
        row = rank_stride_evidence(b"x" * 1100, (21,))["results"][0]
        self.assertEqual(row["disjoint_span_pair_count"], 34)
        self.assertFalse(row["insufficient_pairs"])
        self.assertFalse(row["inconclusive"])


if __name__ == "__main__":
    unittest.main()
