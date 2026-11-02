"""Synthetic SQLite and Windows Tkinter regressions for late search-hit races."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import repair_procedures_gui as gui
from atelierdata import Store
from procedure_search_hits import list_procedure_hits
from procedure_search_navigation import require_live_navigation_target
from repair_procedures import add_step, create_procedure


class FinalSearchNavigationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "search-navigation.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "ONE")
        self.other = self.store.add_vehicle("SYNTHETIC", "TWO")
        self.pid = create_procedure(
            self.store, self.vehicle, "TEST", "Synthetic procedure",
            source="OWNED-SOURCE")
        self.sid = add_step(
            self.store, self.pid, "Synthetic instruction",
            safety_note="WARNING-KEY")

    def warning_hit(self):
        return next(hit for hit in list_procedure_hits(
            self.store, self.vehicle, "WARNING-KEY")
            if hit["field"] == "Avertisment pas")

    def test_final_guard_accepts_live_target_without_writes(self):
        hit = self.warning_hit()
        before = self.store.db.total_changes
        self.assertTrue(require_live_navigation_target(
            self.store, self.vehicle, hit, "WARNING-KEY", self.pid, self.sid))
        self.assertEqual(self.store.db.total_changes, before)

    def test_final_guard_rejects_wrong_gui_selection(self):
        hit = self.warning_hit()
        for pid, sid in ((None, self.sid), (True, self.sid),
                         (self.other, self.sid), (self.pid, None),
                         (self.pid, True), (self.pid, self.sid + 1)):
            with self.subTest(pid=pid, sid=sid), self.assertRaises(ValueError):
                require_live_navigation_target(
                    self.store, self.vehicle, hit, "WARNING-KEY", pid, sid)

    def test_final_guard_rejects_deleted_or_reassigned_hit(self):
        hit = self.warning_hit()
        self.store.db.execute(
            "UPDATE procedures SET vehicle_id=? WHERE id=?",
            (self.other, self.pid))
        self.store.db.commit()
        with self.assertRaises(ValueError):
            require_live_navigation_target(
                self.store, self.vehicle, hit, "WARNING-KEY", self.pid, self.sid)

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
        window.procedure_search_var.set("WARNING-KEY")
        popup = window.open_search_hits()
        self.assertIsNotNone(popup)
        self.addCleanup(lambda: popup.winfo_exists() and popup.destroy())
        popup.hits_tree.selection_set("0")
        return window, popup

    def mutate_during_second_refresh(self, mutation):
        original = gui.list_steps
        calls = [0]

        def raced_list_steps(store, pid):
            rows = original(store, pid)
            calls[0] += 1
            if calls[0] == 2:
                mutation()
            return rows

        return raced_list_steps, calls

    def test_tk_rejects_step_deleted_during_final_refresh(self):
        window, popup = self.open_gui()

        def delete_step():
            self.store.db.execute(
                "DELETE FROM procedure_steps WHERE id=?", (self.sid,))
            self.store.db.commit()

        raced, calls = self.mutate_during_second_refresh(delete_step)
        with patch.object(gui, "list_steps", side_effect=raced), \
                patch("tkinter.messagebox.showerror") as error:
            self.assertIsNone(popup.go_to_hit())
        self.assertGreaterEqual(calls[0], 2)
        error.assert_called_once()
        self.assertFalse(window.steps_tree.exists(str(self.sid)))

    def test_tk_rejects_vehicle_reassigned_during_final_refresh(self):
        window, popup = self.open_gui()

        def move_procedure():
            self.store.db.execute(
                "UPDATE procedures SET vehicle_id=? WHERE id=?",
                (self.other, self.pid))
            self.store.db.commit()

        raced, calls = self.mutate_during_second_refresh(move_procedure)
        with patch.object(gui, "list_steps", side_effect=raced), \
                patch("tkinter.messagebox.showerror") as error:
            self.assertIsNone(popup.go_to_hit())
        self.assertGreaterEqual(calls[0], 2)
        error.assert_called_once()
        self.assertFalse(window.steps_tree.exists(str(self.sid)))

    def test_tk_current_hit_still_navigates(self):
        window, popup = self.open_gui()
        before = self.store.db.total_changes
        result = popup.go_to_hit()
        self.assertEqual(result["step_id"], self.sid)
        self.assertEqual(window.steps_tree.selection(), (str(self.sid),))
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
