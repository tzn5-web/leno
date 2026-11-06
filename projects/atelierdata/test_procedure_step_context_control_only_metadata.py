"""Control-only metadata must never silently hide safety or provenance warnings."""
import sqlite3
import unittest
from types import SimpleNamespace
from procedure_step_context import step_context_text


class ControlOnlyMetadataTests(unittest.TestCase):
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
            INSERT INTO procedures VALUES(1, 10, '', 'Own source');
            INSERT INTO procedure_steps VALUES(2, 1, 1, 'Synthetic instruction', '', 3);
            INSERT INTO articles VALUES(3, 10, 'Own diagram', '');
        """)
        self.store = SimpleNamespace(db=self.db)

    def tearDown(self):
        self.db.close()

    def test_control_only_warning_and_provenance_are_flagged(self):
        for value in ("\x1c", "\x1f", "\u2028", "\u2029"):
            with self.subTest(value=repr(value)):
                self.db.execute("UPDATE procedures SET precautions=? WHERE id=1", (value,))
                self.db.execute("UPDATE articles SET source=? WHERE id=3", (value,))
                before = self.db.total_changes
                rendered = step_context_text(self.store, 10, 1, 2)
                self.assertIn("AVERTISMENT DATE: AVERTISMENT GENERAL", rendered)
                self.assertIn("AVERTISMENT DATE: SURSĂ DOCUMENT", rendered)
                self.assertNotIn(value, rendered)
                self.assertEqual(before, self.db.total_changes)
                self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_empty_optional_metadata_does_not_trigger_warning(self):
        rendered = step_context_text(self.store, 10, 1, 2)
        self.assertNotIn("AVERTISMENT DATE:", rendered)
        self.assertIn("DOCUMENT ASOCIAT: Own diagram", rendered)


if __name__ == "__main__":
    unittest.main()
