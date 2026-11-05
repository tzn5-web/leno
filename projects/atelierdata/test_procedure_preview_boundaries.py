"""Regression checks for Tkinter procedure preview boundaries and navigation IDs."""
import unittest

from repair_procedures_gui import (
    _safe_search_preview,
    _step_tree_values,
    _validate_navigation_id,
)


class ProcedurePreviewBoundaryTests(unittest.TestCase):
    def test_exact_limit_and_one_character_over(self):
        self.assertEqual(_safe_search_preview("ABCDE", 5), "ABCDE")
        self.assertEqual(_safe_search_preview("ABCDEF", 5), "ABCDE")

    def test_control_character_at_truncation_boundary(self):
        self.assertEqual(_safe_search_preview("AB\u202eCD", 4), "AB C")
        self.assertNotIn("\u202e", _safe_search_preview("AB\u202eCD", 4))

    def test_step_fields_are_independently_bounded(self):
        step = {
            "step_number": 1,
            "instruction": "I" * 131,
            "safety_note": "W" * 96,
            "reference_title": "D" * 131,
        }
        number, instruction, warning, reference = _step_tree_values(step)
        self.assertEqual(number, 1)
        self.assertEqual(instruction, "I" * 130)
        self.assertEqual(warning, "W" * 95)
        self.assertEqual(reference, "D" * 130)

    def test_navigation_rejects_bool_float_and_zero(self):
        for value in (True, False, 0, -1, 1.0, "1", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _validate_navigation_id(value, "step")
        self.assertEqual(_validate_navigation_id(42, "step"), 42)


if __name__ == "__main__":
    unittest.main()
