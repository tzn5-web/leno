"""Regression: failed procedure creation must not destroy an editor transaction.

Synthetic vehicle metadata only; no repair specifications or proprietary data.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, ensure_schema, list_procedures


class ProcedureCreationSavepointTests(unittest.TestCase):
    def test_missing_vehicle_keeps_existing_editor_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "creation.sqlite3")
            try:
                ensure_schema(store)
                vehicle = store.add_vehicle("SYNTHETIC", "MODEL", "ENGINE")
                store.db.execute("SAVEPOINT editor_changes")
                try:
                    first = create_procedure(
                        store, vehicle, "Synthetic system", "Pending procedure",
                        source="USER OWNED FIXTURE",
                    )
                    with self.assertRaisesRegex(ValueError, "Vehicle does not exist"):
                        create_procedure(
                            store, 2147483647, "Synthetic system", "Orphan",
                            source="USER OWNED FIXTURE",
                        )
                    self.assertTrue(store.db.in_transaction)
                    self.assertEqual(
                        [row["id"] for row in list_procedures(
                            store, vehicle_id=vehicle, search="Pending procedure"
                        )],
                        [first],
                    )
                    self.assertEqual(
                        store.db.execute(
                            "SELECT COUNT(*) FROM procedures WHERE title='Orphan'"
                        ).fetchone()[0], 0,
                    )
                finally:
                    store.db.execute("ROLLBACK TO SAVEPOINT editor_changes")
                    store.db.execute("RELEASE SAVEPOINT editor_changes")
                self.assertEqual(
                    store.db.execute(
                        "SELECT COUNT(*) FROM procedures WHERE vehicle_id=?", (vehicle,)
                    ).fetchone()[0], 0,
                )
                self.assertEqual(store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
