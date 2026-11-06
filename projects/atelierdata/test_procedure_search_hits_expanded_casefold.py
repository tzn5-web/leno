"""Regression tests for Unicode-expanded search hit preview offsets.

Only synthetic text; these tests do not access proprietary technical data.
"""
import unittest

from procedure_search_hits import _excerpt


class ExpandedCasefoldPreviewTests(unittest.TestCase):
    def test_german_sharp_s_maps_to_one_original_character(self):
        self.assertEqual(_excerpt("pre Straße post", "strasse", radius=0), "…Straße…")

    def test_match_inside_expanded_character_maps_to_original(self):
        self.assertEqual(_excerpt("xßy", "ss", radius=0), "…ß…")

    def test_turkish_dotted_i_expansion_keeps_original_character(self):
        self.assertEqual(_excerpt("xİy", "i\u0307", radius=0), "…İ…")

    def test_expansion_with_control_characters_keeps_safe_excerpt(self):
        preview = _excerpt("xStraße\u202ey", "STRASSE", radius=1)
        self.assertIn("Straße", preview)
        self.assertNotIn("\u202e", preview)


if __name__ == "__main__":
    unittest.main()
