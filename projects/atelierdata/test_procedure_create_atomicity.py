"""Atomic procedure creation regression tests with synthetic vehicle data."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from atelierdata import Store
import repair_procedures as procedures


class ProcedureCreateAtomicityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "procedure-create.sqlite3"
        self.store = Store(path)
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("TEST", "MODEL", "ENGINE")
        self.peer = Store(path)
        self.addCleanup(self.peer.close)
        self.peer.db.execute("PRAGMA busy_timeout=0")

    def test_vehicle_validation_holds_writer_lock(self):
        original = self.store.db
        class ConnectionProxy:
            def __init__(self, connection):
                self.connection = connection
            def execute(self, sql, params=()):
                if sql.startswith("SELECT 1 FROM vehicles"):
                    self.assert_locked()
                return self.connection.execute(sql, params)
            def assert_locked(self):
                with self_test.assertRaises(sqlite3.OperationalError) as error:
                    self_peer.db.execute("DELETE FROM vehicles WHERE id=?", (self_vehicle,))
                self_test.assertIn("locked", str(error.exception).lower())
                self_peer.db.rollback()
            def __getattr__(self, name):
                return getattr(self.connection, name)
        self_test = self
        self_peer = self.peer
        self_vehicle = self.vehicle
        with patch.object(self.store, "db", ConnectionProxy(original)):
            pid = procedures.create_procedure(
                self.store, self.vehicle, "Synthetic", "Task", source="OWN TEST")
        self.assertEqual(procedures.get_procedure(self.store, pid)["vehicle_id"], self.vehicle)
        self.assertFalse(self.store.db.in_transaction)

    def test_missing_vehicle_rolls_back_and_releases_lock(self):
        with self.assertRaises(ValueError):
            procedures.create_procedure(
                self.store, 999999, "Synthetic", "Task", source="OWN TEST")
        self.assertFalse(self.store.db.in_transaction)
        self.peer.db.execute("UPDATE vehicles SET model=? WHERE id=?", ("UPDATED", self.vehicle))
        self.peer.db.commit()
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_existing_transaction_keeps_pending_changes(self):
        self.store.db.execute("UPDATE vehicles SET model=? WHERE id=?", ("PENDING", self.vehicle))
        self.assertTrue(self.store.db.in_transaction)
        pid = procedures.create_procedure(
            self.store, self.vehicle, "Synthetic", "Task", source="OWN TEST")
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(procedures.get_procedure(self.store, pid)["vehicle_id"], self.vehicle)
        self.store.db.rollback()
        self.assertIsNone(procedures.get_procedure(self.store, pid))
        self.assertNotEqual(self.store.db.execute(
            "SELECT model FROM vehicles WHERE id=?", (self.vehicle,)).fetchone()[0], "PENDING")

    def test_failed_nested_creation_preserves_caller_transaction(self):
        self.store.db.execute("UPDATE vehicles SET model=? WHERE id=?", ("PENDING", self.vehicle))
        with self.assertRaises(ValueError):
            procedures.create_procedure(
                self.store, 999999, "Synthetic", "Task", source="OWN TEST")
        self.assertTrue(self.store.db.in_transaction)
        self.assertEqual(self.store.db.execute(
            "SELECT model FROM vehicles WHERE id=?", (self.vehicle,)).fetchone()[0], "PENDING")
        self.store.db.rollback()



if __name__ == "__main__":
    unittest.main()
