"""SQLite GUI-context regression: reject unsafe instructions without leaking metadata.

All fixtures are synthetic; no vehicle repair values are supplied.
"""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class StepContextInstructionBoundaryTests(unittest.TestCase):
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
            INSERT INTO procedures VALUES (1, 10, 'Synthetic caution', 'User-authored');
            INSERT INTO procedure_steps VALUES
                (1, 1, 1, 'Synthetic instruction', 'Synthetic warning', NULL);
        """)
        self.store = SimpleNamespace(db=self.db)

    def tearDown(self):
        self.db.close()

    def test_unsafe_instruction_is_rejected_without_database_mutation(self):
        for instruction in ("Step\u2028forged", "Step\u202eforged", "Step\nforged", "   "):
            with self.subTest(instruction=repr(instruction)):
                self.db.execute(
                    "UPDATE procedure_steps SET instruction=? WHERE id=1",
                    (instruction,))
                before = self.db.total_changes
                with self.assertRaises(ValueError):
                    step_context_text(self.store, 10, 1, 1)
                self.assertEqual(self.db.total_changes, before)
                self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_wrong_vehicle_and_step_are_rejected(self):
        for vehicle_id, step_id in ((11, 1), (10, 999)):
            with self.subTest(vehicle_id=vehicle_id, step_id=step_id):
                before = self.db.total_changes
                with self.assertRaises(ValueError):
                    step_context_text(self.store, vehicle_id, 1, step_id)
                self.assertEqual(self.db.total_changes, before)

    def test_valid_romanian_unicode_is_preserved(self):
        self.db.execute(
            "UPDATE procedure_steps SET instruction=? WHERE id=1",
            ("Verificare autorizată: șurub, țeavă, încălzire",))
        result = step_context_text(self.store, 10, 1, 1)
        self.assertIn("PAS 1: Verificare autorizată: șurub, țeavă, încălzire", result)
        self.assertIn("ATENȚIE LA ACEST PAS: Synthetic warning", result)


if __name__ == "__main__":
    unittest.main()
