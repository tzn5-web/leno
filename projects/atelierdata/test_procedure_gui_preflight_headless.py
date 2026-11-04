"""Headless GUI preflight regression: reject unsafe navigation before Tk windows open.

Uses synthetic SQLite data only. No licensed workshop records or display required.
"""
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from repair_procedures_gui import open_procedures_window


class _NoWindow:
    def Toplevel(self, *args, **kwargs):
        raise AssertionError("GUI window opened before navigation preflight")


class ProcedureGuiPreflightTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.execute(
            "CREATE TABLE procedure_steps (id INTEGER PRIMARY KEY, procedure_id INTEGER)"
        )
        self.connection.execute("INSERT INTO procedure_steps VALUES (101, 10)")
        self.app = SimpleNamespace(
            vid=1, root=object(), tk=_NoWindow(),
            db=SimpleNamespace(db=self.connection)
        )

    def test_invalid_ids_rejected_without_sql_or_window(self):
        statements = []
        self.connection.set_trace_callback(statements.append)
        self.addCleanup(self.connection.set_trace_callback, None)
        for kwargs in (
            {"vehicle_id": True},
            {"vehicle_id": 0},
            {"selected_procedure_id": False},
            {"selected_procedure_id": -1},
            {"selected_step_id": True, "selected_procedure_id": 10},
            {"selected_step_id": 0, "selected_procedure_id": 10},
            {"selected_step_id": 101},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                open_procedures_window(self.app, object, **kwargs)
        self.assertEqual(statements, [])

    def test_foreign_procedure_rejected_before_step_query(self):
        with patch("repair_procedures_gui.get_procedure",
                   return_value={"vehicle_id": 2}) as lookup:
            with self.assertRaisesRegex(ValueError, "vehiculului"):
                open_procedures_window(
                    self.app, object, selected_procedure_id=10,
                    selected_step_id=101
                )
        lookup.assert_called_once_with(self.app.db, 10)

    def test_foreign_step_rejected_without_window_or_writes(self):
        before = self.connection.total_changes
        with patch("repair_procedures_gui.get_procedure",
                   return_value={"vehicle_id": 1}):
            with self.assertRaisesRegex(ValueError, "Pasul nu aparține"):
                open_procedures_window(
                    self.app, object, selected_procedure_id=10,
                    selected_step_id=999
                )
        self.assertEqual(self.connection.total_changes, before)


if __name__ == "__main__":
    unittest.main()
