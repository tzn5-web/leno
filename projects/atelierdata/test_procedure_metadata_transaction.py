"""Regression: caller-owned SQLite savepoint survives invalid procedure edits.

All fixtures are synthetic; no vehicle specifications or licensed content.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import (
    ensure_schema, create_procedure, update_procedure, list_procedures,
)


class ProcedureMetadataTransactionTests(unittest.TestCase):
    def test_invalid_update_does_not_erase_pending_valid_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "synthetic.sqlite3")
            try:
                ensure_schema(store)
                vehicle = store.add_vehicle("SYNTHETIC", "TEST", "NO REAL DATA")
                procedure = create_procedure(
                    store, vehicle, "Demo", "Initial", source="USER-OWNED TEST"
                )
                store.db.execute("SAVEPOINT editor")
                try:
                    update_procedure(
                        store, procedure, "Demo", "Pending edit",
                        source="USER-OWNED TEST"
                    )
                    with self.assertRaises(ValueError):
                        update_procedure(
                            store, procedure, "Demo", "Invalid source", source=""
                        )
                    current = store.db.execute(
                        "SELECT title FROM procedures WHERE id=?", (procedure,)
                    ).fetchone()[0]
                    self.assertEqual(current, "Pending edit")
                    self.assertTrue(store.db.in_transaction)
                    self.assertEqual(
                        len(list_procedures(store, vehicle_id=vehicle, search="Pending edit")),
                        1,
                    )
                finally:
                    store.db.execute("ROLLBACK TO SAVEPOINT editor")
                    store.db.execute("RELEASE SAVEPOINT editor")
                title = store.db.execute(
                    "SELECT title FROM procedures WHERE id=?", (procedure,)
                ).fetchone()[0]
                self.assertEqual(title, "Initial")
                self.assertEqual(store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
