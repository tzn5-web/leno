"""Regression tests for search paging and literal vehicle-scoped results.

Run from projects/atelierdata with: python -m unittest test_search_paging_regression
No OEM data is used.
"""
import unittest
from procedure_search_hits import filter_hit_indices, next_hit_index, _excerpt


class SearchPagingRegression(unittest.TestCase):
    def test_filter_keeps_original_positions(self):
        hits = [{"field": "A"}, {"field": "B"}, {"field": "A"}]
        self.assertEqual(filter_hit_indices(hits, "A"), [0, 2])
        self.assertEqual(len(hits), 3)

    def test_wrap_in_filtered_page(self):
        indices = [0, 2]
        self.assertEqual(indices[next_hit_index(len(indices), 1, 1)], 0)
        self.assertEqual(indices[next_hit_index(len(indices), 0, -1)], 2)

    def test_unicode_casefold_excerpt_offsets(self):
        # Earlier expansion must not shift the match or cut its first letter.
        self.assertEqual(_excerpt("ß abcneedle", "needle", radius=0), "needle")
        # A casefold match can span fewer original characters than the query.
        self.assertEqual(_excerpt("Straße", "SSE", radius=0), "ße")
        self.assertEqual(_excerpt("İstanbul", "stan", radius=0), "stan")
        self.assertEqual(_excerpt("abc", "missing", radius=2), "abc")

    def test_excerpt_preserves_literal_match(self):
        self.assertIn("100%_", _excerpt("prefix 100%_ suffix", "100%_"))


if __name__ == "__main__":
    unittest.main()
