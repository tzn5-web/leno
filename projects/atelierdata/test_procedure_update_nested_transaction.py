"""Regression tests for procedure updates inside caller-owned SQLite transactions."""
import sqlite3
import unittest
from types import SimpleNamespace

from repair_procedures import update_procedure


class UpdateProcedureTransactionTests(unittest.TestCase):
    def setUp(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute("""CREATE TABLE procedures (
            id INTEGER PRIMARY KEY, vehicle_id INTEGER, system TEXT,
            title TEXT, summary TEXT, precautions TEXT, source TEXT)""")
        db.execute("INSERT INTO procedures VALUES (1,1,'System','Original','','','Own source')")
        db.commit()
        self.store = SimpleNamespace(db=db)

    def test_success_preserves_outer_transaction_and_rollback(self):
        db = self.store.db
        db.execute("BEGIN")
        db.execute("UPDATE procedures SET summary='Caller pending' WHERE id=1")
        update_procedure(self.store, 1, "System", "Updated", "New summary",
                         "Caution", "Own source")
        self.assertTrue(db.in_transaction)
        self.assertEqual(db.execute("SELECT title FROM procedures WHERE id=1").fetchone()[0], "Updated")
        db.rollback()
        self.assertEqual(db.execute("SELECT title,summary FROM procedures WHERE id=1").fetchone(),
                         ("Original", ""))

    def test_missing_procedure_does_not_rollback_caller_changes(self):
        db = self.store.db
        db.execute("BEGIN")
        db.execute("UPDATE procedures SET summary='Caller pending' WHERE id=1")
        with self.assertRaisesRegex(ValueError, "Procedure does not exist"):
            update_procedure(self.store, 999, "System", "Updated", source="Own source")
        self.assertTrue(db.in_transaction)
        self.assertEqual(db.execute("SELECT summary FROM procedures WHERE id=1").fetchone()[0],
                         "Caller pending")
        db.rollback()

    def test_standalone_update_commits(self):
        update_procedure(self.store, 1, "System", "Updated", source="Own source")
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(self.store.db.execute("SELECT title FROM procedures WHERE id=1").fetchone()[0],
                         "Updated")


if __name__ == "__main__":
    unittest.main()
