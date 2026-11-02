"""Regression tests for warning-to-step navigation using synthetic data only."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from atelierdata import Store
from repair_procedures import create_procedure, add_step
from procedure_warning_navigation import warning_step_targets
from repair_procedures_gui import open_procedures_window


class WarningStepNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "warnings.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "A")
        self.foreign = self.store.add_vehicle("SYNTHETIC", "B")
        self.procedure = create_procedure(
            self.store, self.vehicle, "TEST", "Synthetic procedure",
            source="USER-OWNED FIXTURE")
        self.first = add_step(
            self.store, self.procedure, "Synthetic first instruction",
            safety_note="Synthetic first warning")
        self.middle = add_step(self.store, self.procedure, "Synthetic second instruction")
        self.last = add_step(
            self.store, self.procedure, "Synthetic third instruction",
            safety_note="Synthetic last warning")

    def targets(self):
        return warning_step_targets(self.store, self.vehicle, self.procedure)

    def test_targets_are_ordered_and_read_only(self):
        before = self.store.db.total_changes
        self.assertEqual(
            self.targets(),
            ((self.first, 1, "Synthetic first warning"),
             (self.last, 3, "Synthetic last warning")))
        self.assertEqual(self.store.db.total_changes, before)

    def test_no_warning_procedure_returns_empty_not_foreign_data(self):
        other = create_procedure(
            self.store, self.vehicle, "TEST", "Empty warning procedure",
            source="USER-OWNED FIXTURE")
        self.assertEqual(
            warning_step_targets(self.store, self.vehicle, other), ())

    def test_reject_foreign_deleted_and_non_integer_ids(self):
        for vehicle, procedure in (
            (self.foreign, self.procedure),
            (self.vehicle, 9999999),
            (True, self.procedure),
            (self.vehicle, True),
            (self.vehicle, str(self.procedure)),
            (float(self.vehicle), self.procedure),
            (self.vehicle, 0),
        ):
            with self.subTest(vehicle=vehicle, procedure=procedure):
                with self.assertRaises(ValueError):
                    warning_step_targets(self.store, vehicle, procedure)

    def test_removed_warning_disappears_on_live_query(self):
        self.store.db.execute(
            "UPDATE procedure_steps SET safety_note='' WHERE id=?", (self.first,))
        self.store.db.commit()
        self.assertEqual(
            self.targets(), ((self.last, 3, "Synthetic last warning"),))

    def open_window(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.vehicle)
        window = open_procedures_window(
            app, object, selected_procedure_id=self.procedure)
        self.addCleanup(lambda: window.winfo_exists() and window.destroy())
        popup = window.open_warning_overview()
        self.assertIsNotNone(popup)
        self.addCleanup(lambda: popup.winfo_exists() and popup.destroy())
        return window, popup

    def test_gui_jumps_to_live_warning_step_without_sqlite_writes(self):
        window, popup = self.open_window()
        self.assertEqual(
            popup.warning_steps.get_children(),
            (str(self.first), str(self.last)))
        before = self.store.db.total_changes
        popup.warning_steps.selection_set(str(self.last))
        self.assertEqual(popup.goto_warning_step(), self.last)
        self.assertEqual(window.steps_tree.selection(), (str(self.last),))
        self.assertIn(
            "Synthetic last warning",
            window.procedure_detail_text.get("1.0", "end"))
        self.assertEqual(self.store.db.total_changes, before)

    def test_gui_refuses_warning_removed_after_popup_opened(self):
        window, popup = self.open_window()
        popup.warning_steps.selection_set(str(self.first))
        self.store.db.execute(
            "UPDATE procedure_steps SET safety_note='' WHERE id=?", (self.first,))
        self.store.db.commit()
        before = self.store.db.total_changes
        with patch("tkinter.messagebox.showinfo") as notice:
            self.assertIsNone(popup.goto_warning_step())
        notice.assert_called_once()
        self.assertNotIn(str(self.first), popup.warning_steps.get_children())
        self.assertEqual(self.store.db.total_changes, before)

    def test_gui_clears_warning_targets_when_procedure_reassigned(self):
        window, popup = self.open_window()
        popup.warning_steps.selection_set(str(self.last))
        self.store.db.execute(
            "UPDATE procedures SET vehicle_id=? WHERE id=?",
            (self.foreign, self.procedure))
        self.store.db.commit()
        before = self.store.db.total_changes
        with patch("tkinter.messagebox.showinfo"):
            self.assertIsNone(popup.goto_warning_step())
        self.assertEqual(popup.warning_steps.get_children(), ())
        self.assertNotIn(
            "Synthetic last warning", popup.overview_text.get("1.0", "end"))
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
