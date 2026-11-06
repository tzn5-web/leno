"""Regression tests for exact search preview boundaries and display-only sanitization.

Synthetic strings only. These tests never access workshop documents or .IDF data.
"""
import unittest

from procedure_search_hits import _excerpt


class SearchPreviewBoundaryRegressionTests(unittest.TestCase):
    def test_match_at_start_with_zero_context(self):
        self.assertEqual(_excerpt("Schemă final", "schemă", radius=0), "Schemă…")

    def test_match_at_end_with_zero_context(self):
        self.assertEqual(_excerpt("prefix Schemă", "schemă", radius=0), "…Schemă")

    def test_expanding_casefold_maps_to_original_character(self):
        self.assertEqual(_excerpt("aßb", "ss", radius=0), "…ß…")
        self.assertEqual(_excerpt("aİb", "i\u0307", radius=0), "…İ…")

    def test_display_sanitization_does_not_shift_match(self):
        original = "A\u202eB Schemă\nC"
        preview = _excerpt(original, "schemă", radius=2)
        self.assertIn("Schemă", preview)
        self.assertNotIn("\u202e", preview)
        self.assertNotIn("\n", preview)
        self.assertEqual(original, "A\u202eB Schemă\nC")

    def test_no_match_has_bounded_safe_prefix(self):
        self.assertEqual(_excerpt("ab\ncd ef", "absent", radius=2), "ab c")


if __name__ == "__main__":
    unittest.main()
