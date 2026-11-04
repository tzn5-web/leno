"""Regression checks for single-line GUI search snippets (no Tk display required)."""
import unittest
from repair_procedures_gui import _safe_search_preview


class SearchPreviewSafetyTests(unittest.TestCase):
    def test_controls_and_bidi_markers_are_neutralized(self):
        raw = "Sursă\nPAS FALS\r\x00\u202eINVERS\u2066"
        result = _safe_search_preview(raw)
        self.assertEqual(result, "Sursă PAS FALS   INVERS")
        self.assertNotIn("\n", result)
        self.assertNotIn("\u202e", result)

    def test_romanian_text_and_limits(self):
        self.assertEqual(_safe_search_preview("  Înlocuiește garnitura  "), "Înlocuiește garnitura")
        self.assertEqual(_safe_search_preview("abcdef", 3), "abc")
        self.assertEqual(_safe_search_preview(None), "")
        for invalid in (0, -1, True, "4"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    _safe_search_preview("abc", invalid)


if __name__ == "__main__":
    unittest.main()
