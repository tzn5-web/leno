"""Regression tests for deterministic step navigation with imperfect imported ordering.

All records are synthetic; no proprietary repair specifications are used.
"""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_navigation import adjacent_step_id


class StepNavigationOrderingRegression(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE procedures(id INTEGER PRIMARY KEY, vehicle_id INTEGER);
            CREATE TABLE procedure_steps(
                id INTEGER PRIMARY KEY, procedure_id INTEGER, step_number INTEGER
            );
            INSERT INTO procedures VALUES (10, 1), (20, 1), (30, 2);
            INSERT INTO procedure_steps VALUES
                (104,10,2), (103,10,1), (102,10,1), (101,10,3),
                (201,20,1), (301,30,1);
        """)
        self.store = SimpleNamespace(db=self.db)

    def test_duplicate_step_numbers_use_id_as_stable_tiebreaker(self):
        before = self.db.total_changes
        order = []
        current = None
        while True:
            current = adjacent_step_id(self.store, 1, 10, current, 1)
            if current is None:
                break
            order.append(current)
        self.assertEqual(order, [102, 103, 104, 101])
        self.assertEqual(adjacent_step_id(self.store, 1, 10, None, -1), 101)
        self.assertEqual(adjacent_step_id(self.store, 1, 10, 103, -1), 102)
        self.assertEqual(self.db.total_changes, before)

    def test_empty_owned_procedure_and_foreign_step(self):
        self.db.execute("INSERT INTO procedures VALUES (40, 1)")
        self.assertIsNone(adjacent_step_id(self.store, 1, 40))
        self.assertIsNone(adjacent_step_id(self.store, 1, 40, direction=-1))
        with self.assertRaisesRegex(ValueError, "Step no longer belongs"):
            adjacent_step_id(self.store, 1, 10, 201)
        with self.assertRaisesRegex(ValueError, "selected vehicle"):
            adjacent_step_id(self.store, 1, 30)

    def test_live_tie_reordering_is_observed_without_cache(self):
        self.assertEqual(adjacent_step_id(self.store, 1, 10), 102)
        self.db.execute("UPDATE procedure_steps SET step_number=0 WHERE id=104")
        self.assertEqual(adjacent_step_id(self.store, 1, 10), 104)
        self.assertEqual(adjacent_step_id(self.store, 1, 10, 104), 102)


if __name__ == "__main__":
    unittest.main()
