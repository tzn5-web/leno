"""Validate search preview radius limits independently of Tkinter.

Synthetic values only; no workshop documents or proprietary databases.
"""
import unittest
from procedure_search_hits import _excerpt


class SearchPreviewRadiusTests(unittest.TestCase):
    def test_invalid_radius_is_rejected(self):
        for radius in (-1, 1001, True, False, 1.5, "85", None):
            with self.subTest(radius=radius):
                with self.assertRaises(ValueError):
                    _excerpt("Schemă proprie", "schemă", radius=radius)

    def test_zero_radius_keeps_matched_text(self):
        self.assertEqual(_excerpt("prefix schemă sufix", "schemă", radius=0), "…schemă…")

    def test_maximum_radius_retains_unicode_and_neutralizes_controls(self):
        preview = _excerpt("A\\nSchemă\\u202eB", "schemă", radius=1000)
        self.assertIn("Schemă", preview)
        self.assertNotIn("\\n", preview)
        self.assertNotIn("\\u202e", preview)


if __name__ == "__main__":
    unittest.main()
