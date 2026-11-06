"""Search excerpts must not inject invisible controls into the Windows GUI."""
import unittest
from procedure_search_hits import _excerpt, _safe_excerpt_display


class ProcedureSearchPreviewSafetyTests(unittest.TestCase):
    def test_controls_are_neutralized_in_matching_excerpt(self):
        for control in ("\x00", "\x1c", "\u200e", "\u2028", "\u2029", "\ud800"):
            with self.subTest(control=repr(control)):
                result = _excerpt("Înainte " + control + "schemă după", "schemă")
                self.assertIn("schemă", result)
                self.assertNotIn(control, result)
                self.assertIn("Înainte", result)

    def test_no_match_fallback_is_safe(self):
        result = _excerpt("document\u202e propriu\nvalid", "absent")
        self.assertNotIn("\u202e", result)
        self.assertNotIn("\n", result)
        self.assertIn("document", result)

    def test_unicode_text_and_hit_identity_unchanged(self):
        self.assertEqual(_excerpt("Reparație și schemă", "schemă"), "Reparație și schemă")
        self.assertEqual(_safe_excerpt_display("A\u2028B"), "A B")


if __name__ == "__main__":
    unittest.main()
