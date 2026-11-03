"""SQLite navigation contract: one read snapshot, no writes, strict IDs.

Synthetic fixtures only; independent of licensed technical content.
"""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_navigation import adjacent_step_id


class NavigationReadOnlyContract(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE procedures(id INTEGER PRIMARY KEY, vehicle_id INTEGER);
            CREATE TABLE procedure_steps(
                id INTEGER PRIMARY KEY, procedure_id INTEGER, step_number INTEGER
            );
            INSERT INTO procedures VALUES (10, 1), (20, 2);
            INSERT INTO procedure_steps VALUES (101, 10, 1), (102, 10, 2);
        """)
        self.store = SimpleNamespace(db=self.db)

    def test_one_select_per_navigation_without_mutation(self):
        statements = []
        self.db.set_trace_callback(statements.append)
        self.addCleanup(self.db.set_trace_callback, None)
        before = self.db.total_changes
        self.assertEqual(adjacent_step_id(self.store, 1, 10, 101), 102)
        self.assertEqual(len(statements), 1, statements)
        self.assertTrue(statements[0].lstrip().upper().startswith("SELECT "))
        self.assertEqual(self.db.total_changes, before)

    def test_invalid_identifiers_and_directions_rejected_before_sql(self):
        statements = []
        self.db.set_trace_callback(statements.append)
        self.addCleanup(self.db.set_trace_callback, None)
        for args in (
            (True, 10, None, 1),
            (1, False, None, 1),
            (0, 10, None, 1),
            (1, 0, None, 1),
            (1, 10, True, 1),
            (1, 10, 0, 1),
            (1, 10, None, True),
            (1, 10, None, 0),
            (1, 10, None, 2),
            ("1", 10, None, 1),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                adjacent_step_id(self.store, *args)
        self.assertEqual(statements, [])

    def test_deleted_step_is_rejected_not_redirected(self):
        self.db.execute("DELETE FROM procedure_steps WHERE id=101")
        with self.assertRaisesRegex(ValueError, "Step no longer belongs"):
            adjacent_step_id(self.store, 1, 10, 101)
        self.assertEqual(adjacent_step_id(self.store, 1, 10), 102)

    def test_foreign_vehicle_and_missing_procedure_rejected(self):
        for vehicle, procedure in ((2, 10), (1, 20), (1, 999)):
            with self.subTest(vehicle=vehicle, procedure=procedure):
                with self.assertRaisesRegex(ValueError, "selected vehicle"):
                    adjacent_step_id(self.store, vehicle, procedure)


if __name__ == "__main__":
    unittest.main()
