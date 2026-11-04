"""Regression for the exact SQLite reorder/restore sequence in Windows GUI smoke.

Uses synthetic instructions only; does not depend on a display server.
"""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import (
    ensure_schema, create_procedure, add_step, move_step, delete_step, list_steps,
)
from repair_procedures_gui import _step_tree_values


class ProcedureReorderRestoreRegression(unittest.TestCase):
    def test_temporary_step_restores_original_identity_and_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "reorder.sqlite3")
            try:
                ensure_schema(store)
                vehicle = store.add_vehicle("SYNTHETIC", "TEST", "DEMO")
                procedure = create_procedure(
                    store, vehicle, "Synthetic system", "Synthetic procedure",
                    "Demo only", "Not a real repair", "Synthetic source",
                )
                original = add_step(store, procedure, "Original synthetic step")
                before = [(r["id"], r["step_number"]) for r in list_steps(store, procedure)]
                temporary = add_step(store, procedure, "Temporary synthetic step")
                self.assertEqual(
                    [r["id"] for r in list_steps(store, procedure)], [original, temporary]
                )
                self.assertTrue(move_step(store, temporary, -1))
                self.assertEqual(
                    [r["id"] for r in list_steps(store, procedure)], [temporary, original]
                )
                self.assertTrue(move_step(store, temporary, 1))
                self.assertEqual(
                    [r["id"] for r in list_steps(store, procedure)], [original, temporary]
                )
                delete_step(store, temporary)
                restored = list_steps(store, procedure)
                self.assertEqual(
                    [(r["id"], r["step_number"]) for r in restored], before,
                    "Deleting a GUI smoke temporary step must restore original SQLite rows",
                )
                self.assertEqual(_step_tree_values(restored[0])[0], 1)
                self.assertEqual(store.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
