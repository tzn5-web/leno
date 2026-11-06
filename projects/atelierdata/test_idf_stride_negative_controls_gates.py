"""Synthetic-only regression for conservative negative-control evidence gates."""
import unittest
from unittest.mock import patch
from idf_stride_negative_controls import rank_stride_evidence


class NegativeControlGates(unittest.TestCase):
    def test_empty_candidates_rejected(self):
        with self.assertRaises(ValueError):
            rank_stride_evidence(b"synthetic", strides=())

    def test_sparse_perfect_match_still_inconclusive(self):
        def fake_compare(sample, strides):
            return {"hypotheses": {str(s): {
                "possible_window_pairs": 2 if s == 19 else 50,
                "matching_window_pairs": 2 if s == 19 else 0,
                "low_diversity_confounder": False,
                "global_periodicity_confounder": False,
                "qualified_runs": 1,
            } for s in strides}}
        with patch("idf_stride_negative_controls.compare_stride_hypotheses", fake_compare):
            row = rank_stride_evidence(b"x" * 100, strides=(19,))["results"][0]
        self.assertTrue(row["insufficient_pairs"])
        self.assertTrue(row["inconclusive"])
        self.assertFalse(row["record_format_proven"])

    def test_weak_margin_inconclusive(self):
        def fake_compare(sample, strides):
            return {"hypotheses": {str(s): {
                "possible_window_pairs": 100,
                "matching_window_pairs": 51 if s == 19 else 50,
                "low_diversity_confounder": False,
                "global_periodicity_confounder": False,
                "qualified_runs": 1,
            } for s in strides}}
        with patch("idf_stride_negative_controls.compare_stride_hypotheses", fake_compare):
            row = rank_stride_evidence(b"x" * 200, strides=(19,))["results"][0]
        self.assertTrue(row["weak_control_margin"])
        self.assertTrue(row["inconclusive"])


if __name__ == "__main__":
    unittest.main()
