"""Regression tests for incomplete user-authored repair instructions."""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class IncompleteStepContextTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE procedures (id INTEGER PRIMARY KEY, vehicle_id INTEGER,
                                     precautions TEXT, source TEXT);
            CREATE TABLE procedure_steps (id INTEGER PRIMARY KEY, procedure_id INTEGER,
                                          step_number INTEGER, instruction TEXT,
                                          safety_note TEXT, article_id INTEGER);
            CREATE TABLE articles (id INTEGER PRIMARY KEY, vehicle_id INTEGER,
                                   title TEXT, source TEXT);
            INSERT INTO procedures VALUES (1, 10, 'Synthetic warning', NULL);
            INSERT INTO procedure_steps VALUES (1, 1, 1, NULL, NULL, NULL);
            INSERT INTO procedure_steps VALUES (2, 1, 2, '  ', NULL, NULL);
            INSERT INTO procedure_steps VALUES (3, 1, 3, 'Synthetic authorized step', NULL, NULL);
        """)
        self.store = SimpleNamespace(db=self.db)

    def tearDown(self):
        self.db.close()

    def test_missing_and_whitespace_instructions_fail_closed(self):
        before = self.db.total_changes
        for step_id in (1, 2):
            with self.subTest(step_id=step_id), self.assertRaisesRegex(ValueError, "instruction"):
                step_context_text(self.store, 10, 1, step_id)
        self.assertEqual(self.db.total_changes, before)

    def test_missing_procedure_source_is_not_rendered_as_none(self):
        before = self.db.total_changes
        rendered = step_context_text(self.store, 10, 1, 3)
        self.assertIn("Synthetic authorized step", rendered)
        self.assertIn("Synthetic warning", rendered)
        self.assertNotIn("SURSĂ PROCEDURĂ: None", rendered)
        self.assertNotIn("SURSĂ PROCEDURĂ:", rendered)
        self.assertEqual(self.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
