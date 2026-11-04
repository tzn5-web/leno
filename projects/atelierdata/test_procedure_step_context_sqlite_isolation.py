"""SQLite integration tests for vehicle-scoped repair-step context.

Fixtures contain only synthetic, user-authored text; no technical repair values.
"""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class StepContextIsolationTests(unittest.TestCase):
    def setUp(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE procedures (
                id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL,
                precautions TEXT, source TEXT
            );
            CREATE TABLE procedure_steps (
                id INTEGER PRIMARY KEY, procedure_id INTEGER NOT NULL,
                step_number INTEGER, instruction TEXT, safety_note TEXT,
                article_id INTEGER
            );
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL,
                title TEXT, source TEXT
            );
            INSERT INTO procedures VALUES (1, 10, 'Use appropriate protection', 'Author A');
            INSERT INTO procedures VALUES (2, 20, '', 'Author B');
            INSERT INTO articles VALUES (1, 20, 'PRIVATE OTHER VEHICLE', 'PRIVATE SOURCE');
            INSERT INTO articles VALUES (2, 10, 'Licensed diagram', 'Licensed author');
            INSERT INTO procedure_steps VALUES
                (1, 1, 1, 'Synthetic instruction', 'Synthetic caution', 1),
                (2, 1, 2, 'Next synthetic step', '', 2),
                (3, 2, 1, 'Other vehicle step', '', NULL);
        """)
        self.db = db
        self.store = SimpleNamespace(db=db)

    def tearDown(self):
        self.db.close()

    def test_foreign_document_is_not_disclosed_and_warning_is_visible(self):
        before = self.db.total_changes
        result = step_context_text(self.store, 10, 1, 1)
        self.assertIn("Synthetic instruction", result)
        self.assertIn("Use appropriate protection", result)
        self.assertIn("Synthetic caution", result)
        self.assertIn("AVERTISMENT REFERINȚĂ", result)
        self.assertNotIn("PRIVATE OTHER VEHICLE", result)
        self.assertNotIn("PRIVATE SOURCE", result)
        self.assertEqual(self.db.total_changes, before)

    def test_owned_document_includes_licensed_provenance(self):
        result = step_context_text(self.store, 10, 1, 2)
        self.assertIn("Licensed diagram", result)
        self.assertIn("Licensed author", result)
        self.assertNotIn("AVERTISMENT REFERINȚĂ", result)

    def test_cross_vehicle_step_and_invalid_ids_are_rejected(self):
        before = self.db.total_changes
        for args in ((10, 2, 3), (20, 1, 1), (10, 1, 3),
                     (True, 1, 1), (10, 1, False), (10, 1, "1")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                step_context_text(self.store, *args)
        self.assertEqual(self.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
