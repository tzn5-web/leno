"""Boundary tests for search preview mapping; synthetic text only.

The GUI must show the original character even when casefold expands it.
No workshop data, files or database mutations are involved.
"""
import unittest

from procedure_search_hits import _excerpt


class SearchPreviewBoundaryTests(unittest.TestCase):
    def test_expansion_at_start_and_end(self):
        self.assertEqual(_excerpt("ß", "SS", radius=0), "ß")
        self.assertEqual(_excerpt("İ", "i\u0307", radius=0), "İ")

    def test_match_after_multiple_expansions(self):
        text = "ß" * 80 + "PROCEDURA" + "İ" * 80
        preview = _excerpt(text, "procedura", radius=2)
        self.assertEqual(preview, "…ßßPROCEDURAİİ…")

    def test_preview_is_readable_without_control_chars(self):
        preview = _excerpt("a\u202eb\nStraße\u200dc", "STRASSE", radius=5)
        self.assertIn("Straße", preview)
        self.assertNotIn("\u202e", preview)
        self.assertNotIn("\u200d", preview)
        self.assertNotIn("\n", preview)

    def test_invalid_radius_does_not_silently_truncate(self):
        for radius in (-1, 1001, True, 2.5, "5", None):
            with self.subTest(radius=radius):
                with self.assertRaises(ValueError):
                    _excerpt("test", "test", radius=radius)


if __name__ == "__main__":
    unittest.main()
