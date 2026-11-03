"""Nested transaction regression tests using only synthetic repair data."""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step, list_steps


class AddStepNestedTransactionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / "nested-step.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("TEST", "MODEL", "ENGINE")
        self.pid = create_procedure(self.store, self.vehicle, "Test", "Synthetic", source="OWN TEST")

    def test_success_does_not_commit_caller_transaction(self):
        self.store.db.execute("UPDATE vehicles SET model=? WHERE id=?", ("PENDING", self.vehicle))
        sid = add_step(self.store, self.pid, "Synthetic instruction")
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(list_steps(self.store, self.pid)[0]["id"], sid)
        self.store.db.rollback()
        self.assertEqual(list_steps(self.store, self.pid), [])
        self.assertNotEqual(self.store.db.execute(
            "SELECT model FROM vehicles WHERE id=?", (self.vehicle,)).fetchone()[0], "PENDING")

    def test_failed_add_does_not_rollback_caller_changes(self):
        self.store.db.execute("UPDATE vehicles SET model=? WHERE id=?", ("PENDING", self.vehicle))
        with self.assertRaises(ValueError):
            add_step(self.store, self.pid, "Synthetic instruction", position=999)
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(self.store.db.execute(
            "SELECT model FROM vehicles WHERE id=?", (self.vehicle,)).fetchone()[0], "PENDING")
        self.assertEqual(list_steps(self.store, self.pid), [])
        self.store.db.rollback()


if __name__ == "__main__":
    unittest.main()
