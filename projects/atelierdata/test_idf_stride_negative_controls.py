import unittest

from idf_stride_negative_controls import rank_stride_evidence


class NegativeControlsTests(unittest.TestCase):
    def test_constant_buffer_is_inconclusive(self):
        result = rank_stride_evidence(b"X" * 400)
        self.assertTrue(all(r["inconclusive"] for r in result["results"]))
        self.assertFalse(result["idf_decoder_proven"])

    def test_short_buffer_is_inconclusive(self):
        result = rank_stride_evidence(b"abc")
        self.assertTrue(all(r["inconclusive"] for r in result["results"]))

    def test_reject_duplicate_candidates(self):
        with self.assertRaises(ValueError):
            rank_stride_evidence(b"abc", (19, 19))

    def test_overlapping_windows_do_not_count_as_independent_pairs(self):
        # 240 raw pair opportunities are fewer than 32 disjoint 8-byte
        # opportunities, even if every overlapping window matches.
        result = rank_stride_evidence(b"A" * 266, (19,))
        row = result["results"][0]
        self.assertGreater(row["nonoverlapping_pair_upper_bound"], 0)
        self.assertLess(row["nonoverlapping_pair_upper_bound"], 32)
        self.assertTrue(row["insufficient_pairs"])
        self.assertTrue(row["inconclusive"])

    def test_empty_sample_reports_zero_effective_pairs(self):
        row = rank_stride_evidence(b"", (21,))["results"][0]
        self.assertEqual(row["nonoverlapping_pair_upper_bound"], 0)
        self.assertTrue(row["insufficient_pairs"])

    def test_aggregate_only(self):
        result = rank_stride_evidence(bytes(range(200)))
        self.assertNotIn("motif", str(result).lower())
        self.assertNotIn("offset", str(result).lower())
        self.assertEqual([r["stride"] for r in result["results"]], [19, 21])


if __name__ == "__main__":
    unittest.main()
