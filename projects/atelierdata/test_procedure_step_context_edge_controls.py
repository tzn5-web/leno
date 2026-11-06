"""Regression for stripped Unicode control characters in procedure GUI metadata."""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class StrippedControlBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE procedures(id INTEGER PRIMARY KEY, vehicle_id INTEGER,
                                    precautions TEXT, source TEXT);
            CREATE TABLE procedure_steps(id INTEGER PRIMARY KEY, procedure_id INTEGER,
                                         step_number INTEGER, instruction TEXT,
                                         safety_note TEXT, article_id INTEGER);
            CREATE TABLE articles(id INTEGER PRIMARY KEY, vehicle_id INTEGER,
                                  title TEXT, source TEXT);
            INSERT INTO procedures VALUES(1, 10, 'Safe warning', 'Own source');
            INSERT INTO procedure_steps VALUES(2, 1, 1, 'Safe instruction', 'Safe note', 3);
            INSERT INTO articles VALUES(3, 10, 'Own diagram', 'Own provenance');
        """)
        self.store = SimpleNamespace(db=self.db)

    def tearDown(self):
        self.db.close()

    def test_controls_at_edges_of_metadata_are_rejected_not_stripped(self):
        for control in ("\x1c", "\x1d", "\x1e", "\x1f"):
            with self.subTest(control=repr(control)):
                self.db.execute("UPDATE procedures SET precautions=? WHERE id=1",
                                (control + "Do not trust" + control,))
                self.db.execute("UPDATE articles SET source=? WHERE id=3",
                                (control + "Unverified provenance",))
                before = self.db.total_changes
                text = step_context_text(self.store, 10, 1, 2)
                self.assertIn("AVERTISMENT DATE: AVERTISMENT GENERAL", text)
                self.assertIn("AVERTISMENT DATE: SURSĂ DOCUMENT", text)
                self.assertNotIn("Do not trust", text)
                self.assertNotIn("Unverified provenance", text)
                self.assertEqual(before, self.db.total_changes)
                self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_instruction_with_edge_control_is_rejected(self):
        self.db.execute("UPDATE procedure_steps SET instruction=? WHERE id=2",
                        ("\x1c" + "Synthetic instruction",))
        with self.assertRaisesRegex(ValueError, "forbidden control"):
            step_context_text(self.store, 10, 1, 2)


if __name__ == "__main__":
    unittest.main()
