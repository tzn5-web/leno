"""Transactional regression tests for synthetic repair procedures only."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import (
    ensure_schema, create_procedure, add_step, update_step,
    delete_step, move_step, list_steps,
)


class ProcedureTransactionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "procedures.sqlite3")
        self.addCleanup(self.store.close)
        ensure_schema(self.store)
        vehicle = self.store.add_vehicle("SYNTHETIC", "TEST", "NO REAL DATA")
        self.procedure = create_procedure(
            self.store, vehicle, "Demo", "Transaction boundaries",
            source="USER-OWNED SYNTHETIC TEST",
        )

    def snapshot(self):
        return [(r["id"], r["step_number"], r["instruction"])
                for r in list_steps(self.store, self.procedure)]

    def test_caller_rollback_restores_insert_update_reorder_and_delete(self):
        first = add_step(self.store, self.procedure, "Synthetic A")
        second = add_step(self.store, self.procedure, "Synthetic B")
        original = self.snapshot()
        self.store.db.execute("SAVEPOINT caller_scope")
        try:
            inserted = add_step(self.store, self.procedure, "Synthetic C", position=2)
            update_step(self.store, first, "Synthetic A edited")
            self.assertTrue(move_step(self.store, second, -1))
            delete_step(self.store, inserted)
            self.assertNotEqual(self.snapshot(), original)
        finally:
            self.store.db.execute("ROLLBACK TO SAVEPOINT caller_scope")
            self.store.db.execute("RELEASE SAVEPOINT caller_scope")
        self.assertEqual(self.snapshot(), original)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_failed_nested_write_preserves_caller_changes(self):
        first = add_step(self.store, self.procedure, "Synthetic first")
        self.store.db.execute("SAVEPOINT caller_scope")
        try:
            second = add_step(self.store, self.procedure, "Synthetic second")
            before = self.snapshot()
            with self.assertRaises(ValueError):
                update_step(self.store, first, "Invalid foreign document", article_id=99999999)
            with self.assertRaises(ValueError):
                add_step(self.store, self.procedure, "Invalid position", position=999)
            self.assertEqual(self.snapshot(), before)
            self.assertIn(second, [row[0] for row in self.snapshot()])
            self.assertTrue(self.store.db.in_transaction)
        finally:
            self.store.db.execute("ROLLBACK TO SAVEPOINT caller_scope")
            self.store.db.execute("RELEASE SAVEPOINT caller_scope")
        self.assertEqual(len(self.snapshot()), 1)
        self.assertEqual(self.snapshot()[0][0], first)


if __name__ == "__main__":
    unittest.main()
