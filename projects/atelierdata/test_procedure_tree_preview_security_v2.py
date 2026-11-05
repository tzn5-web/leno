"""Regression checks for Tk tree previews with untrusted local documentation.

Synthetic strings only; no proprietary vehicle data.
"""
from __future__ import annotations

import unittest

from repair_procedures_gui import _safe_search_preview, _step_tree_values


class ProcedureTreePreviewSecurityTests(unittest.TestCase):
    def test_bidi_controls_and_line_breaks_do_not_enter_tree(self):
        raw = "START\u202eREVERSED\u202c\nNEXT\r\tEND\u2067RTL\u2069"
        preview = _safe_search_preview(raw)
        self.assertEqual(preview, "START REVERSED  NEXT  END RTL ")
        self.assertFalse(any(c in preview for c in ("\u202e", "\u202c", "\u2067", "\u2069", "\n")))

    def test_each_step_column_has_its_own_bound(self):
        step = {
            "step_number": 3,
            "instruction": "I" * 200,
            "safety_note": "W" * 200,
            "reference_title": "D" * 200,
        }
        number, instruction, warning, reference = _step_tree_values(step)
        self.assertEqual(number, 3)
        self.assertEqual((len(instruction), len(warning), len(reference)), (130, 95, 130))

    def test_invalid_step_numbers_and_missing_optional_values(self):
        for number in (True, 0, -1, 1.5, "1", None):
            with self.subTest(number=number):
                values = _step_tree_values({
                    "step_number": number,
                    "instruction": None,
                    "safety_note": None,
                    "reference_title": None,
                })
                self.assertEqual(values, ("", "", "", ""))

    def test_preview_rejects_invalid_limits(self):
        for limit in (True, 0, -1, 1.5, "10", None):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    _safe_search_preview("text", limit)


if __name__ == "__main__":
    unittest.main()
