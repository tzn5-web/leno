"""Nested SQLite transaction regression tests for step deletion (synthetic data)."""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step, delete_step, list_steps


class DeleteStepNestedTransactionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / "delete-step.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("TEST", "MODEL", "ENGINE")
        self.procedure = create_procedure(
            self.store, self.vehicle, "Test", "Synthetic", source="OWN TEST"
        )
        self.first = add_step(self.store, self.procedure, "First")
        self.second = add_step(self.store, self.procedure, "Second")

    def test_delete_preserves_caller_transaction_and_rollback(self):
        self.store.db.execute(
            "UPDATE vehicles SET model=? WHERE id=?", ("PENDING", self.vehicle)
        )
        delete_step(self.store, self.first)
        self.assertTrue(self.store.db.in_transaction)
        remaining = list_steps(self.store, self.procedure)
        self.assertEqual([(r["id"], r["step_number"]) for r in remaining],
                         [(self.second, 1)])
        self.store.db.rollback()
        self.assertEqual(
            [(r["id"], r["step_number"]) for r in list_steps(self.store, self.procedure)],
            [(self.first, 1), (self.second, 2)],
        )
        self.assertEqual(self.store.db.execute(
            "SELECT model FROM vehicles WHERE id=?", (self.vehicle,)
        ).fetchone()[0], "MODEL")

    def test_missing_step_does_not_commit_caller_transaction(self):
        self.store.db.execute(
            "UPDATE vehicles SET model=? WHERE id=?", ("PENDING", self.vehicle)
        )
        delete_step(self.store, self.second + 99999)
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(len(list_steps(self.store, self.procedure)), 2)
        self.store.db.rollback()
        self.assertEqual(self.store.db.execute(
            "SELECT model FROM vehicles WHERE id=?", (self.vehicle,)
        ).fetchone()[0], "MODEL")


if __name__ == "__main__":
    unittest.main()
