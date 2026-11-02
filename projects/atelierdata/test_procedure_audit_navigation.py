"""Synthetic SQLite and Windows Tkinter tests for stale audit navigation."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import repair_procedures_gui as gui
from atelierdata import Store
from procedure_audit import audit_procedure
from procedure_audit_navigation import require_live_audit_step
from repair_procedures import add_step, create_procedure


class AuditNavigationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "audit-navigation.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "ONE")
        self.other = self.store.add_vehicle("SYNTHETIC", "TWO")
        self.pid = create_procedure(
            self.store, self.vehicle, "TEST", "Synthetic procedure",
            source="USER-OWNED TEST SOURCE")
        self.sid = add_step(self.store, self.pid, "Synthetic instruction")
        self.set_number(3)

    def set_number(self, number):
        self.store.db.execute(
            "UPDATE procedure_steps SET step_number=? WHERE id=?",
            (number, self.sid))
        self.store.db.commit()

    def finding(self):
        return next(item for item in audit_procedure(
            self.store, self.pid)["issues"]
            if item["code"] == "STEP_ORDER_INVALID")

    def test_live_finding_is_read_only(self):
        issue = self.finding()
        before = self.store.db.total_changes
        self.assertEqual(require_live_audit_step(
            self.store, self.vehicle, self.pid, issue), self.sid)
        self.assertEqual(self.store.db.total_changes, before)

    def test_resolved_finding_cannot_navigate(self):
        issue = self.finding()
        self.set_number(1)
        with self.assertRaisesRegex(ValueError, "no longer current"):
            require_live_audit_step(self.store, self.vehicle, self.pid, issue)

    def test_reassigned_procedure_cannot_navigate(self):
        issue = self.finding()
        self.store.db.execute(
            "UPDATE procedures SET vehicle_id=? WHERE id=?",
            (self.other, self.pid))
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError, "selected vehicle"):
            require_live_audit_step(self.store, self.vehicle, self.pid, issue)

    def test_invalid_ids_and_forged_findings_rejected(self):
        issue = self.finding()
        for bad in (None, True, "1", 1.0, 0, -1):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                require_live_audit_step(self.store, bad, self.pid, issue)
            with self.subTest(pid=repr(bad)), self.assertRaises(ValueError):
                require_live_audit_step(self.store, self.vehicle, bad, issue)
        for bad_issue in (None, {}, {"step_id": True}, {"step_id": -1},
                          {**issue, "code": "FAKE_FINDING"}):
            with self.subTest(issue=repr(bad_issue)), self.assertRaises(ValueError):
                require_live_audit_step(
                    self.store, self.vehicle, self.pid, bad_issue)

    def open_gui(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.vehicle)
        window = gui.open_procedures_window(
            app, object, selected_procedure_id=self.pid)
        self.addCleanup(lambda: window.winfo_exists() and window.destroy())
        audit = window.open_procedure_audit()
        self.assertIsNotNone(audit)
        self.addCleanup(lambda: audit.winfo_exists() and audit.destroy())
        index = next(i for i, issue in enumerate(audit.audit_report["issues"])
                     if issue["code"] == "STEP_ORDER_INVALID")
        audit.issues_tree.selection_set(str(index))
        return window, audit

    def test_tk_navigates_only_current_finding(self):
        window, audit = self.open_gui()
        before = self.store.db.total_changes
        self.assertEqual(audit.go_to_step(), self.sid)
        self.assertEqual(window.steps_tree.selection(), (str(self.sid),))
        self.assertEqual(self.store.db.total_changes, before)

    def test_tk_rejects_finding_resolved_after_audit_open(self):
        window, audit = self.open_gui()
        self.set_number(1)
        with patch("tkinter.messagebox.showerror") as error:
            self.assertIsNone(audit.go_to_step())
        error.assert_called_once()
        self.assertNotEqual(window.steps_tree.selection(), (str(self.sid),))

    def test_tk_rejects_finding_resolved_during_redraw(self):
        window, audit = self.open_gui()
        original = gui.list_steps
        calls = [0]

        def raced_list_steps(store, pid):
            rows = original(store, pid)
            calls[0] += 1
            if calls[0] == 1:
                self.set_number(1)
            return rows

        with patch.object(gui, "list_steps", side_effect=raced_list_steps), \
                patch("tkinter.messagebox.showerror") as error:
            self.assertIsNone(audit.go_to_step())
        self.assertGreaterEqual(calls[0], 1)
        error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
