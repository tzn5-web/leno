"""Regression tests for imported/corrupt step metadata at the GUI context boundary."""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class StepContextIntegrityTests(unittest.TestCase):
    def setUp(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE procedures (id INTEGER PRIMARY KEY, vehicle_id INTEGER,
              precautions TEXT, source TEXT);
            CREATE TABLE procedure_steps (id INTEGER PRIMARY KEY, procedure_id INTEGER,
              step_number, instruction TEXT, safety_note TEXT, article_id INTEGER);
            CREATE TABLE articles (id INTEGER PRIMARY KEY, vehicle_id INTEGER,
              title TEXT, source TEXT);
            INSERT INTO procedures VALUES (1, 10, '', 'licensed-test-source');
            INSERT INTO procedure_steps VALUES (2, 1, 1, 'Synthetic instruction', '', NULL);
        """)
        self.db = db
        self.store = SimpleNamespace(db=db)

    def tearDown(self):
        self.db.close()

    def test_invalid_imported_step_numbers_rejected(self):
        for value in (0, -1, 'one', 1.5, None):
            with self.subTest(value=value):
                self.db.execute("UPDATE procedure_steps SET step_number=? WHERE id=2", (value,))
                with self.assertRaisesRegex(ValueError, "Step number"):
                    step_context_text(self.store, 10, 1, 2)

    def test_nul_instruction_rejected_and_valid_whitespace_trimmed(self):
        self.db.execute("UPDATE procedure_steps SET instruction=? WHERE id=2",
                        ("synthetic\x00unsafe",))
        with self.assertRaisesRegex(ValueError, "NUL"):
            step_context_text(self.store, 10, 1, 2)
        self.db.execute("UPDATE procedure_steps SET instruction=?,step_number=1 WHERE id=2",
                        ("  Synthetic instruction  ",))
        rendered = step_context_text(self.store, 10, 1, 2)
        self.assertIn("PAS 1: Synthetic instruction", rendered)
        self.assertNotIn("  Synthetic instruction  ", rendered)


if __name__ == "__main__":
    unittest.main()
