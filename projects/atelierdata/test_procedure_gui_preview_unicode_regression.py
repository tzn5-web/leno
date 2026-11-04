"""Headless regression tests for Windows procedure tree previews.

No vehicle data or proprietary documentation is bundled.
"""
import unittest

from repair_procedures_gui import _step_tree_values


class ProcedurePreviewUnicodeRegressionTests(unittest.TestCase):
    def test_control_characters_cannot_create_fake_rows_or_reverse_warning(self):
        step = {
            "step_number": 1,
            "instruction": "Verificare\nPAS FALS\u202eXYZ\u202c",
            "safety_note": "ATENȚIE\r\n\u2066ascuns\u2069",
            "reference_title": "Schemă\u0085\u202aexternă\u202c",
        }
        values = _step_tree_values(step)
        self.assertEqual(values[0], 1)
        for value in values[1:]:
            self.assertNotIn("\n", value)
            self.assertNotIn("\r", value)
            self.assertTrue(all(not (ord(ch) < 32 or 127 <= ord(ch) <= 159)
                                for ch in value))
            self.assertTrue(all(ch not in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
                                for ch in value))
        self.assertIn("Verificare PAS FALS", values[1])
        self.assertIn("Schemă", values[3])

    def test_corrupt_optional_fields_do_not_crash_preview(self):
        values = _step_tree_values({
            "step_number": True,
            "instruction": None,
            "safety_note": 42,
            "reference_title": {"invalid": "title"},
        })
        self.assertEqual(values, ("", "", "", ""))


if __name__ == "__main__":
    unittest.main()
