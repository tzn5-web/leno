"""Headless tests for the step tree preview used by the Windows Tk interface."""
import sqlite3
import unittest

from repair_procedures_gui import _step_tree_values


class StepTreePreviewTests(unittest.TestCase):
    def test_nullable_columns_and_valid_number(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        self.addCleanup(db.close)
        db.execute("CREATE TABLE preview (step_number INTEGER, instruction TEXT, safety_note TEXT, reference_title TEXT)")
        db.execute("INSERT INTO preview VALUES (1, '  Inspect component  ', NULL, NULL)")
        before = db.total_changes
        row = db.execute("SELECT * FROM preview").fetchone()
        self.assertEqual(_step_tree_values(row), (1, "Inspect component", "", ""))
        self.assertEqual(db.total_changes, before)

    def test_controls_cannot_forge_extra_tree_lines(self):
        row = {"step_number": 2, "instruction": "Inspect" + chr(10) + "PAS 99: forged",
               "safety_note": "Warning" + chr(13) + "Injected",
               "reference_title": "Diagram" + chr(0) + "name"}
        values = _step_tree_values(row)
        self.assertEqual(values, (2, "Inspect PAS 99: forged", "Warning Injected", "Diagram name"))
        for value in values[1:]:
            for code in (0, 10, 13):
                self.assertNotIn(chr(code), value)

    def test_invalid_values_and_bounded_preview(self):
        row = {"step_number": True, "instruction": "x" * 200,
               "safety_note": 123, "reference_title": object()}
        self.assertEqual(_step_tree_values(row), ("", "x" * 130, "", ""))


if __name__ == "__main__":
    unittest.main()
