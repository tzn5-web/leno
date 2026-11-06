"""SQLite regression for document provenance after vehicle reassignment.

Only synthetic user-authored content is used.
"""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class StepContextReferenceReassignmentTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE procedures (
                id INTEGER PRIMARY KEY, vehicle_id INTEGER,
                precautions TEXT, source TEXT);
            CREATE TABLE procedure_steps (
                id INTEGER PRIMARY KEY, procedure_id INTEGER,
                step_number INTEGER, instruction TEXT,
                safety_note TEXT, article_id INTEGER);
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY, vehicle_id INTEGER,
                title TEXT, source TEXT);
            INSERT INTO procedures VALUES
                (1, 10, 'Synthetic safety notice', 'Own procedure');
            INSERT INTO articles VALUES
                (7, 10, 'Synthetic diagram', 'Licensed synthetic source');
            INSERT INTO procedure_steps VALUES
                (3, 1, 1, 'Synthetic instruction', 'Step warning', 7);
        """)
        self.store = SimpleNamespace(db=self.db)

    def tearDown(self):
        self.db.close()

    def test_reassigned_document_does_not_leak_title_or_provenance(self):
        before = step_context_text(self.store, 10, 1, 3)
        self.assertIn("DOCUMENT ASOCIAT: Synthetic diagram", before)
        self.assertIn("SURSĂ DOCUMENT: Licensed synthetic source", before)

        self.db.execute("UPDATE articles SET vehicle_id=11 WHERE id=7")
        changes = self.db.total_changes
        after = step_context_text(self.store, 10, 1, 3)

        self.assertIn("PAS 1: Synthetic instruction", after)
        self.assertIn("ATENȚIE LA ACEST PAS: Step warning", after)
        self.assertIn("AVERTISMENT REFERINȚĂ: Document indisponibil", after)
        self.assertNotIn("Synthetic diagram", after)
        self.assertNotIn("Licensed synthetic source", after)
        self.assertEqual(self.db.total_changes, changes)
        self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_missing_document_is_flagged_without_leaking_source(self):
        self.db.execute("DELETE FROM articles WHERE id=7")
        result = step_context_text(self.store, 10, 1, 3)
        self.assertIn("AVERTISMENT REFERINȚĂ: Document indisponibil", result)
        self.assertNotIn("SURSĂ DOCUMENT:", result)
        self.assertIn("SURSĂ PROCEDURĂ: Own procedure", result)


if __name__ == "__main__":
    unittest.main()
