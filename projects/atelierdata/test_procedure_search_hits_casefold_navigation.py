"""Regression coverage for Unicode casefold hit positions and stable navigation.

Synthetic inputs only; no proprietary workshop content.
"""
import unittest

from procedure_search_hits import _excerpt, filter_hit_indices, next_hit_index


class SearchHitCasefoldNavigationTests(unittest.TestCase):
    def test_expanding_casefold_keeps_original_match(self):
        preview = _excerpt("A" * 100 + "Straße" + "B" * 100, "STRASSE", radius=6)
        self.assertIn("Straße", preview)
        self.assertTrue(preview.startswith("…"))
        self.assertTrue(preview.endswith("…"))

    def test_casefold_with_multiline_control_is_safe(self):
        preview = _excerpt("prefix\nStraße\u202esuffix", "STRASSE", radius=20)
        self.assertIn("Straße", preview)
        self.assertNotIn("\n", preview)
        self.assertNotIn("\u202e", preview)

    def test_filtered_indices_preserve_original_row_ids(self):
        hits = [{"field": "Avertisment pas"}, {"field": "Instrucțiune pas"},
                {"field": "Avertisment pas"}]
        self.assertEqual(filter_hit_indices(hits, "Avertisment pas"), [0, 2])
        self.assertEqual(next_hit_index(2, 1), 0)
        self.assertEqual(next_hit_index(2, 0, -1), 1)
        self.assertEqual(len(hits), 3)

    def test_invalid_navigation_parameters_rejected(self):
        for count, current, direction in [(True, None, 1), (1, True, 1),
                                           (1, 0, True), (0, 0, 1)]:
            with self.subTest(count=count, current=current, direction=direction):
                with self.assertRaises(ValueError):
                    next_hit_index(count, current, direction)


if __name__ == "__main__":
    unittest.main()
