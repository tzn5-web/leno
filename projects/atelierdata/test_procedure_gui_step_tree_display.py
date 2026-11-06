"""Regression checks for safe Windows procedure step rows (synthetic data only)."""
import unittest

from repair_procedures_gui import _safe_search_preview, _step_tree_values


class ProcedureTreeDisplayTests(unittest.TestCase):
    def test_step_tree_neutralizes_controls_without_changing_input(self):
        step = {
            "step_number": 2,
            "instruction": "Verifică\u202e ordinea\npașilor",
            "safety_note": "Atenție\x00: oprește operația",
            "reference_title": "Schemă\u2066 electrică\u2069",
        }
        original = dict(step)
        row = _step_tree_values(step)
        self.assertEqual(row[0], 2)
        self.assertEqual(row[1], "Verifică  ordinea pașilor")
        self.assertEqual(row[2], "Atenție : oprește operația")
        self.assertEqual(row[3], "Schemă  electrică")
        self.assertEqual(step, original)

    def test_step_tree_rejects_boolean_or_invalid_step_numbers(self):
        base = {"instruction": "Pas", "safety_note": "", "reference_title": ""}
        for number in (True, 0, -1, "3", None):
            with self.subTest(number=number):
                self.assertEqual(_step_tree_values({**base, "step_number": number})[0], "")

    def test_gui_preview_caps_length_after_control_neutralization(self):
        self.assertEqual(_safe_search_preview("  abc\n\u202eDEF  ", 7), "abc  DE")
        with self.assertRaises(ValueError):
            _safe_search_preview("text", True)
        with self.assertRaises(ValueError):
            _safe_search_preview("text", 0)


if __name__ == "__main__":
    unittest.main()
