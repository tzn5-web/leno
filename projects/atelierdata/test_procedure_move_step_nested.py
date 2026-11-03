"""Nested SQLite transaction regression tests for step reordering (synthetic data)."""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step, move_step, list_steps


class MoveStepNestedTransactionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / "move-step.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("TEST", "MODEL", "ENGINE")
        self.procedure = create_procedure(
            self.store, self.vehicle, "Test", "Synthetic", source="OWN TEST"
        )
        self.first = add_step(self.store, self.procedure, "First")
        self.second = add_step(self.store, self.procedure, "Second")

    def _order(self):
        return [(row["id"], row["step_number"]) for row in
                list_steps(self.store, self.procedure)]

    def _pending_edit(self):
        self.store.db.execute(
            "UPDATE vehicles SET model=? WHERE id=?", ("PENDING", self.vehicle)
        )

    def _assert_rollback(self):
        self.store.db.rollback()
        self.assertEqual(self._order(), [(self.first, 1), (self.second, 2)])
        self.assertEqual(self.store.db.execute(
            "SELECT model FROM vehicles WHERE id=?", (self.vehicle,)
        ).fetchone()[0], "MODEL")

    def test_move_preserves_outer_transaction_and_rollback(self):
        self._pending_edit()
        self.assertTrue(move_step(self.store, self.first, 1))
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(self._order(), [(self.second, 1), (self.first, 2)])
        self._assert_rollback()

    def test_boundary_move_does_not_commit_outer_transaction(self):
        self._pending_edit()
        self.assertFalse(move_step(self.store, self.first, -1))
        self.assertTrue(self.store.db.in_transaction)
        self._assert_rollback()

    def test_missing_step_rolls_back_only_own_savepoint(self):
        self._pending_edit()
        with self.assertRaises(ValueError):
            move_step(self.store, self.second + 99999, 1)
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(self.store.db.execute(
            "SELECT model FROM vehicles WHERE id=?", (self.vehicle,)
        ).fetchone()[0], "PENDING")
        self._assert_rollback()


if __name__ == "__main__":
    unittest.main()
