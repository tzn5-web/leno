"""Regression checks for Unicode display controls in Tk procedure previews."""
import unittest
from repair_procedures_gui import _step_tree_values


class UnicodePreviewTests(unittest.TestCase):
    def test_c1_and_bidi_controls_are_neutralized(self):
        row = {"step_number": 3,
               "instruction": "Check" + chr(0x85) + "pump" + chr(0x202e) + "reverse",
               "safety_note": "Alert" + chr(0x2066) + "text" + chr(0x2069),
               "reference_title": "Diagram" + chr(0x9f) + "source"}
        self.assertEqual(_step_tree_values(row),
                         (3, "Check pump reverse", "Alert text", "Diagram source"))

    def test_normal_unicode_text_is_preserved(self):
        row = {"step_number": 4, "instruction": "Verifică presiunea — fără valori implicite",
               "safety_note": "Atenție: temperatură ridicată",
               "reference_title": "Schemă autorizată"}
        self.assertEqual(_step_tree_values(row)[1:],
                         (row["instruction"], row["safety_note"], row["reference_title"]))


if __name__ == "__main__":
    unittest.main()
