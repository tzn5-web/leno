"""Behavioral checks for safe Tkinter previews of licensed procedure data."""
import unittest

from repair_procedures_gui import _safe_search_preview, _step_tree_values


class ProcedureTreePreviewTests(unittest.TestCase):
    def test_untrusted_control_and_bidi_text_is_neutralized(self):
        raw = "Inspect\nconnector\r\t\u202eREVERSED\u2066\u2069\u0085\u2028next"
        result = _safe_search_preview(raw)
        self.assertEqual(result, "Inspect connector   REVERSED   next")
        self.assertNotIn("\n", result)

    def test_preview_limit_validation_rejects_bool_and_nonpositive(self):
        for limit in (True, False, 0, -1, 1.5, "20", None):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    _safe_search_preview("data", limit)

    def test_non_text_values_do_not_become_gui_metadata(self):
        for value in (None, 12, False, {"source": "private"}):
            with self.subTest(value=value):
                self.assertEqual(_safe_search_preview(value), "")

    def test_step_row_keeps_valid_number_and_bounds_each_field(self):
        row = {
            "step_number": 3,
            "instruction": "I" * 300 + "\u202e",
            "safety_note": "S" * 300,
            "reference_title": "R" * 300,
        }
        number, instruction, warning, title = _step_tree_values(row)
        self.assertEqual(number, 3)
        self.assertEqual((len(instruction), len(warning), len(title)), (130, 95, 130))
        self.assertNotIn("\u202e", instruction)

    def test_invalid_step_number_is_not_displayed(self):
        for number in (True, 0, -2, "3", None):
            with self.subTest(number=number):
                row = dict(step_number=number, instruction=None,
                           safety_note=None, reference_title=None)
                self.assertEqual(_step_tree_values(row), ("", "", "", ""))


if __name__ == "__main__":
    unittest.main()
