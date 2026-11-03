"""Regression checks for procedure deletion and caller-owned SQLite transactions."""
import sqlite3
import unittest
from types import SimpleNamespace

from repair_procedures import delete_procedure


class DeleteProcedureTransactionTests(unittest.TestCase):
    def setUp(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
            CREATE TABLE procedures(id INTEGER PRIMARY KEY, title TEXT);
            CREATE TABLE procedure_steps(
                id INTEGER PRIMARY KEY,
                procedure_id INTEGER REFERENCES procedures(id) ON DELETE CASCADE);
            INSERT INTO procedures VALUES (1, 'Synthetic procedure');
            INSERT INTO procedure_steps VALUES (1, 1);
        """)
        self.store = SimpleNamespace(db=db)

    def test_delete_inside_caller_transaction_can_be_rolled_back(self):
        db = self.store.db
        db.execute("BEGIN")
        db.execute("INSERT INTO procedures VALUES (2, 'Caller pending')")
        delete_procedure(self.store, 1)
        self.assertTrue(db.in_transaction)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM procedure_steps").fetchone()[0], 0)
        db.rollback()
        self.assertEqual(db.execute("SELECT id FROM procedures ORDER BY id").fetchall(), [(1,)])
        self.assertEqual(db.execute("SELECT id FROM procedure_steps").fetchall(), [(1,)])

    def test_missing_delete_does_not_commit_caller_transaction(self):
        db = self.store.db
        db.execute("BEGIN")
        db.execute("INSERT INTO procedures VALUES (2, 'Caller pending')")
        delete_procedure(self.store, 999)
        self.assertTrue(db.in_transaction)
        db.rollback()
        self.assertEqual(db.execute("SELECT id FROM procedures").fetchall(), [(1,)])

    def test_standalone_delete_commits_cascade(self):
        delete_procedure(self.store, 1)
        self.assertFalse(self.store.db.in_transaction)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM procedures").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM procedure_steps").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
