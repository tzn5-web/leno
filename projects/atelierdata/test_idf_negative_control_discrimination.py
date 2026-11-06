"""Synthetic negative-control regression: a stride must beat its neighbors."""
import unittest
from unittest.mock import patch
from idf_stride_negative_controls import rank_stride_evidence


class NegativeControlDiscriminationTests(unittest.TestCase):
    def _run(self, candidate_matches, neighbor_matches):
        def row(matches):
            return {"possible_window_pairs": 100, "matching_window_pairs": matches,
                    "low_diversity_confounder": False,
                    "global_periodicity_confounder": False, "qualified_runs": 3}
        payload = {"hypotheses": {"19": row(candidate_matches),
                                  "18": row(neighbor_matches),
                                  "20": row(neighbor_matches)}}
        with patch("idf_stride_negative_controls.compare_stride_hypotheses", return_value=payload):
            return rank_stride_evidence(b"x" * 256, strides=(19,))["results"][0]

    def test_equal_control_is_inconclusive(self):
        self.assertTrue(self._run(20, 20)["inconclusive"])

    def test_worse_than_control_is_inconclusive(self):
        self.assertTrue(self._run(10, 20)["inconclusive"])

    def test_better_than_controls_is_not_automatically_proof(self):
        row = self._run(30, 20)
        self.assertFalse(row["inconclusive"])
        self.assertFalse(row["record_format_proven"])


if __name__ == "__main__":
    unittest.main()
