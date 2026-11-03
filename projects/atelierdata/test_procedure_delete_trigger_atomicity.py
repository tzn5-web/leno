"""Atomic deletion regression: a database trigger must not erase caller edits.

Synthetic SQLite fixtures only; no technical repair values.
"""
import sqlite3
import unittest
from types import SimpleNamespace

from repair_procedures import delete_procedure


class DeleteProcedureTriggerFailureTests(unittest.TestCase):
    def setUp(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript("""
            CREATE TABLE procedures(id INTEGER PRIMARY KEY, title TEXT);
            INSERT INTO procedures VALUES (1, 'Synthetic procedure');
            CREATE TRIGGER reject_procedure_delete
            BEFORE DELETE ON procedures
            BEGIN SELECT RAISE(ABORT, 'synthetic delete rejection'); END;
        """)
        self.store = SimpleNamespace(db=db)

    def test_trigger_failure_preserves_caller_transaction(self):
        db = self.store.db
        db.execute("BEGIN")
        db.execute("INSERT INTO procedures VALUES (2, 'Pending caller edit')")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "synthetic delete rejection"):
            delete_procedure(self.store, 1)
        self.assertTrue(db.in_transaction)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM procedures").fetchone()[0], 2)
        db.rollback()
        self.assertEqual(db.execute("SELECT id FROM procedures").fetchall(), [(1,)])

    def test_trigger_failure_rolls_back_standalone_operation(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, "synthetic delete rejection"):
            delete_procedure(self.store, 1)
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(self.store.db.execute("SELECT id FROM procedures").fetchall(), [(1,)])


if __name__ == "__main__":
    unittest.main()
