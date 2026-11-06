"""Tk tree preview must not render imported Unicode controls or surrogates."""
import unittest

from repair_procedures_gui import _safe_search_preview, _step_tree_values


class TkPreviewUnicodeTests(unittest.TestCase):
    def test_control_categories_are_replaced_without_losing_romanian_text(self):
        for char in ("\u202e", "\u2066", "\u200b", "\ud800", "\u2028", "\u2029", "\x1f"):
            with self.subTest(character=ascii(char)):
                rendered = _safe_search_preview("Înainte" + char + "după")
                self.assertEqual(rendered, "Înainte după")
                self.assertNotIn(char, rendered)

    def test_tree_values_never_expose_unpaired_surrogate_or_bidi(self):
        row = {
            "step_number": 1,
            "instruction": "Instrucțiune\udfff ascunsă",
            "safety_note": "Atenție\u202e fals",
            "reference_title": "Schemă\u200b proprie",
        }
        values = _step_tree_values(row)
        self.assertEqual(values, (1, "Instrucțiune  ascunsă",
                                  "Atenție  fals", "Schemă  proprie"))
        for text in values[1:]:
            text.encode("utf-8")

    def test_invalid_limit_is_rejected_even_for_missing_sqlite_values(self):
        # A malformed GUI limit must not be silently accepted just because
        # an optional SQLite column is NULL or has an unexpected type.
        for value in (None, 42, object()):
            for limit in (True, 0, -1, 1.5):
                with self.subTest(value_type=type(value).__name__, limit=limit):
                    with self.assertRaisesRegex(ValueError, "Invalid preview limit"):
                        _safe_search_preview(value, limit)

    def test_invalid_limit_and_non_string_inputs(self):
        self.assertEqual(_safe_search_preview(None), "")
        for limit in (True, 0, -1, 2.0):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    _safe_search_preview("test", limit)
        self.assertEqual(_safe_search_preview("  Încercare  ", 4), "Înce")


if __name__ == "__main__":
    unittest.main()
