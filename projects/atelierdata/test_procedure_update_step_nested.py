"""Regression tests for update_step inside a caller-owned SQLite transaction.

All records are synthetic; no vehicle repair values are supplied.
"""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step, list_steps, update_step


class UpdateStepNestedTransactionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "update-step.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("TEST", "MODEL", "ENGINE")
        self.procedure = create_procedure(
            self.store, self.vehicle, "Test", "Synthetic", source="OWN TEST"
        )
        self.step = add_step(self.store, self.procedure, "Before")

    def test_success_keeps_caller_transaction_uncommitted(self):
        self.store.db.execute(
            "UPDATE vehicles SET model=? WHERE id=?", ("PENDING", self.vehicle)
        )
        update_step(self.store, self.step, "After")
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(list_steps(self.store, self.procedure)[0]["instruction"], "After")
        self.store.db.rollback()
        self.assertEqual(list_steps(self.store, self.procedure)[0]["instruction"], "Before")
        self.assertEqual(
            self.store.db.execute(
                "SELECT model FROM vehicles WHERE id=?", (self.vehicle,)
            ).fetchone()[0],
            "MODEL",
        )

    def test_failed_update_keeps_caller_changes(self):
        self.store.db.execute(
            "UPDATE vehicles SET model=? WHERE id=?", ("PENDING", self.vehicle)
        )
        with self.assertRaises(ValueError):
            update_step(self.store, self.step + 99999, "Missing")
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(
            self.store.db.execute(
                "SELECT model FROM vehicles WHERE id=?", (self.vehicle,)
            ).fetchone()[0],
            "PENDING",
        )
        self.assertEqual(list_steps(self.store, self.procedure)[0]["instruction"], "Before")
        self.store.db.rollback()


if __name__ == "__main__":
    unittest.main()
