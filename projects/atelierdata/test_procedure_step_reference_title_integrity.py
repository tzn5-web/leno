"""SQLite regression for corrupt document titles in repair-step GUI context."""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class StepReferenceTitleIntegrityTests(unittest.TestCase):
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
            INSERT INTO procedures VALUES(1,10,'','Licensed synthetic source');
            INSERT INTO procedure_steps VALUES(1,1,1,'Synthetic instruction','',1);
            INSERT INTO articles VALUES(1,10,'Synthetic diagram','Licensed source');
        """)
        self.store = SimpleNamespace(db=self.db)

    def tearDown(self):
        self.db.close()

    def test_corrupt_and_blank_titles_warn_without_crashing(self):
        for title in (b"\xff", "", "   "):
            with self.subTest(title=title):
                self.db.execute("UPDATE articles SET title=? WHERE id=1", (title,))
                before = self.db.total_changes
                text = step_context_text(self.store, 10, 1, 1)
                self.assertIn("AVERTISMENT REFERINȚĂ:", text)
                self.assertNotIn("DOCUMENT ASOCIAT:", text)
                self.assertNotIn("SURSĂ DOCUMENT:", text)
                self.assertEqual(before, self.db.total_changes)

    def test_valid_title_is_trimmed_and_provenance_retained(self):
        self.db.execute("UPDATE articles SET title='  Synthetic diagram  ' WHERE id=1")
        before = self.db.total_changes
        text = step_context_text(self.store, 10, 1, 1)
        self.assertIn("DOCUMENT ASOCIAT: Synthetic diagram", text)
        self.assertIn("SURSĂ DOCUMENT: Licensed source", text)
        self.assertNotIn("AVERTISMENT REFERINȚĂ:", text)
        self.assertEqual(before, self.db.total_changes)


if __name__ == "__main__":
    unittest.main()
