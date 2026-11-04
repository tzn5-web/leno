"""SQLite regression for safe GUI rendering of untrusted licensed metadata."""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class StepContextControlCharacterTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE procedures (
                id INTEGER PRIMARY KEY, vehicle_id INTEGER, precautions TEXT, source TEXT);
            CREATE TABLE procedure_steps (
                id INTEGER PRIMARY KEY, procedure_id INTEGER, step_number INTEGER,
                instruction TEXT, safety_note TEXT, article_id INTEGER);
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY, vehicle_id INTEGER, title TEXT, source TEXT);
            INSERT INTO procedures VALUES
                (1, 10, 'Safety\\nPAS 999: forged', 'Source\\rforged');
            INSERT INTO articles VALUES
                (1, 10, '  Authorized document  ', 'Source\\nforged');
            INSERT INTO procedure_steps VALUES
                (1, 1, 1, ' Authorized step ', 'Warning\\tforged', 1);
        """)
        self.store = SimpleNamespace(db=self.db)

    def tearDown(self):
        self.db.close()

    def test_control_metadata_does_not_inject_gui_lines(self):
        before = self.db.total_changes
        result = step_context_text(self.store, 10, 1, 1)
        self.assertEqual(result, "PAS 1: Authorized step\\nDOCUMENT ASOCIAT: Authorized document".replace("\\n", "\n"))
        self.assertNotIn("forged", result)
        self.assertEqual(self.db.total_changes, before)

    def test_invalid_document_title_is_not_rendered(self):
        self.db.execute("UPDATE articles SET title=? WHERE id=1", ("Title\\nPAS 2: forged".replace("\\n", "\n"),))
        before = self.db.total_changes
        result = step_context_text(self.store, 10, 1, 1)
        self.assertIn("AVERTISMENT REFERINȚĂ:", result)
        self.assertNotIn("DOCUMENT ASOCIAT:", result)
        self.assertNotIn("forged", result)
        self.assertEqual(self.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
