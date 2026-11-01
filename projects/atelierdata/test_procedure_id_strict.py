"""Synthetic regression: SQLite must never coerce repair IDs to row 1.

No OEM instructions, proprietary databases or licensed documents are used.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import (
    add_step, create_procedure, delete_procedure, delete_step,
    get_procedure, list_reference_articles, list_steps, move_step,
    procedure_text, update_procedure, update_step,
)


class StrictRepairIdentifierTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "ids.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "TEST")
        self.procedure = create_procedure(
            self.store, self.vehicle, "Test system", "Test procedure",
            source="OWNED TEST DATA",
        )
        self.step = add_step(self.store, self.procedure, "Test instruction")

    def snapshot(self):
        return (
            self.store.db.total_changes,
            tuple(tuple(row) for row in self.store.db.execute(
                "SELECT id,vehicle_id,system,title,source FROM procedures ORDER BY id")),
            tuple(tuple(row) for row in self.store.db.execute(
                "SELECT id,procedure_id,step_number,instruction,safety_note,article_id "
                "FROM procedure_steps ORDER BY id")),
        )

    def test_invalid_vehicle_id_cannot_create_procedure(self):
        baseline = self.snapshot()
        for invalid in (True, False, float(self.vehicle), str(self.vehicle),
                        None, 0, -1):
            with self.subTest(value=repr(invalid)):
                with self.assertRaises(ValueError):
                    create_procedure(self.store, invalid, "Other", "Other",
                                     source="OWNED TEST DATA")
                self.assertEqual(self.snapshot(), baseline)

    def test_invalid_procedure_id_cannot_read_or_mutate(self):
        baseline = self.snapshot()
        operations = (
            lambda i: get_procedure(self.store, i),
            lambda i: list_steps(self.store, i),
            lambda i: list_reference_articles(self.store, i),
            lambda i: procedure_text(self.store, i),
            lambda i: add_step(self.store, i, "Other instruction"),
            lambda i: update_procedure(self.store, i, "Other", "Other",
                                       source="OWNED TEST DATA"),
            lambda i: delete_procedure(self.store, i),
        )
        for invalid in (True, False, float(self.procedure),
                        str(self.procedure), None, 0, -1):
            for operation in operations:
                with self.subTest(value=repr(invalid), operation=operation):
                    with self.assertRaises(ValueError):
                        operation(invalid)
                    self.assertEqual(self.snapshot(), baseline)

    def test_invalid_step_id_cannot_mutate(self):
        baseline = self.snapshot()
        operations = (
            lambda i: update_step(self.store, i, "Other instruction"),
            lambda i: delete_step(self.store, i),
            lambda i: move_step(self.store, i, 1),
        )
        for invalid in (True, False, float(self.step), str(self.step),
                        None, 0, -1):
            for operation in operations:
                with self.subTest(value=repr(invalid), operation=operation):
                    with self.assertRaises(ValueError):
                        operation(invalid)
                    self.assertEqual(self.snapshot(), baseline)

    def test_valid_integer_ids_keep_existing_behavior(self):
        self.assertEqual(get_procedure(self.store, self.procedure)["id"],
                         self.procedure)
        self.assertEqual(list_steps(self.store, self.procedure)[0]["id"],
                         self.step)
        update_step(self.store, self.step, "Edited test instruction")
        self.assertIn("Edited test instruction",
                      procedure_text(self.store, self.procedure))
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0],
                         "ok")


if __name__ == "__main__":
    unittest.main()
