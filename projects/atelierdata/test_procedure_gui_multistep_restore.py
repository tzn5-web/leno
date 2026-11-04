"""Multi-step reorder regression for the Windows procedure tree's SQLite backing.

Synthetic workshop content only; no display server or licensed data required.
"""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import (
    ensure_schema, create_procedure, add_step, delete_step, list_steps, move_step,
)
from repair_procedures_gui import _step_tree_values


class ProcedureMultiStepRestoreTests(unittest.TestCase):
    def test_insert_move_both_directions_delete_restores_all_existing_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "procedure-reorder.sqlite3")
            try:
                ensure_schema(store)
                vehicle = store.add_vehicle("SYNTHETIC", "TEST", "DEMO")
                procedure = create_procedure(
                    store, vehicle, "Synthetic", "Reorder regression",
                    source="User-authored synthetic fixture",
                )
                originals = [
                    add_step(store, procedure, f"Original synthetic instruction {n}")
                    for n in range(1, 4)
                ]
                baseline = [
                    (row["id"], row["step_number"], row["instruction"])
                    for row in list_steps(store, procedure)
                ]
                temporary = add_step(
                    store, procedure, "Temporary synthetic instruction", position=2
                )
                self.assertEqual(
                    [r["id"] for r in list_steps(store, procedure)],
                    [originals[0], temporary, originals[1], originals[2]],
                )
                self.assertTrue(move_step(store, temporary, -1))
                self.assertEqual(
                    [r["id"] for r in list_steps(store, procedure)],
                    [temporary, *originals],
                )
                self.assertTrue(move_step(store, temporary, 1))
                self.assertEqual(
                    [r["id"] for r in list_steps(store, procedure)],
                    [originals[0], temporary, originals[1], originals[2]],
                )
                delete_step(store, temporary)
                restored = list_steps(store, procedure)
                self.assertEqual(
                    [(r["id"], r["step_number"], r["instruction"]) for r in restored],
                    baseline,
                )
                self.assertEqual(
                    [str(_step_tree_values(r)[0]) for r in restored],
                    ["1", "2", "3"],
                )
                self.assertEqual(
                    store.db.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
