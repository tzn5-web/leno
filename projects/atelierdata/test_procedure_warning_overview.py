"""Synthetic SQLite and Tkinter regression tests for the warning overview."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from atelierdata import Store
from procedure_warning_overview import warning_overview_text
from repair_procedures import add_step, create_procedure
from repair_procedures_gui import open_procedures_window


class ProcedureWarningOverviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "warning.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "CAR")
        self.foreign = self.store.add_vehicle("OTHER", "CAR")
        self.procedure = create_procedure(
            self.store, self.vehicle, "TEST SYSTEM", "Inert procedure",
            precautions="Synthetic general warning", source="USER-OWNED FIXTURE")
        add_step(self.store, self.procedure, "Inert step one",
                 safety_note="Synthetic step one warning")
        add_step(self.store, self.procedure, "Inert step two")
        add_step(self.store, self.procedure, "Inert step three",
                 safety_note="Synthetic step three warning")

    def overview(self):
        return warning_overview_text(self.store, self.vehicle, self.procedure)

    def test_ordered_warnings_and_provenance_are_read_only(self):
        before = self.store.db.total_changes
        text = self.overview()
        self.assertIn("SURSĂ PROCEDURĂ: USER-OWNED FIXTURE", text)
        self.assertIn("AVERTISMENT GENERAL", text)
        self.assertLess(text.index("PAS 1"), text.index("PAS 3"))
        self.assertNotIn("PAS 2", text)
        self.assertIn("TOTAL AVERTISMENTE ÎNREGISTRATE: 3", text)
        self.assertEqual(self.store.db.total_changes, before)

    def test_empty_warning_index_is_not_a_safety_claim(self):
        other = create_procedure(self.store, self.vehicle, "TEST", "No warnings",
                                 source="USER-OWNED FIXTURE")
        text = warning_overview_text(self.store, self.vehicle, other)
        self.assertIn("TOTAL AVERTISMENTE ÎNREGISTRATE: 0", text)
        self.assertIn("nu confirmă", text)

    def test_reject_foreign_deleted_and_untyped_ids(self):
        before = self.store.db.total_changes
        for bad_vehicle, bad_procedure in (
                (self.foreign, self.procedure), (self.vehicle, 999999),
                (True, self.procedure), (self.vehicle, True),
                (float(self.vehicle), self.procedure),
                (self.vehicle, str(self.procedure)), (0, self.procedure)):
            with self.subTest(vehicle=bad_vehicle, procedure=bad_procedure):
                with self.assertRaises(ValueError):
                    warning_overview_text(self.store, bad_vehicle, bad_procedure)
        self.assertEqual(self.store.db.total_changes, before)

    def test_updates_are_read_live(self):
        self.store.db.execute("UPDATE procedure_steps SET safety_note=? "
                              "WHERE procedure_id=? AND step_number=2",
                              ("New synthetic warning", self.procedure))
        self.store.db.commit()
        self.assertIn("ATENȚIE — PAS 2:\nNew synthetic warning", self.overview())
        self.assertIn("TOTAL AVERTISMENTE ÎNREGISTRATE: 4", self.overview())

    def test_tk_overview_refreshes_and_clears_reassigned_procedure(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.vehicle)
        window = open_procedures_window(
            app, object, selected_procedure_id=self.procedure)
        try:
            popup = window.open_warning_overview()
            self.assertIsNotNone(popup)
            self.assertIn("Synthetic general warning",
                          popup.overview_text.get("1.0", "end"))
            self.store.db.execute("UPDATE procedures SET vehicle_id=? WHERE id=?",
                                  (self.foreign, self.procedure))
            self.store.db.commit()
            before = self.store.db.total_changes
            self.assertIsNone(popup.refresh_overview())
            self.assertNotIn("Synthetic general warning",
                             popup.overview_text.get("1.0", "end"))
            self.assertIn("nu mai aparține", popup.overview_text.get("1.0", "end"))
            self.assertEqual(self.store.db.total_changes, before)
            popup.destroy()
        finally:
            window.destroy()

    def test_tk_rejects_reassignment_during_initial_overview_read(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.vehicle)
        window = open_procedures_window(
            app, object, selected_procedure_id=self.procedure)
        try:
            original = warning_overview_text(self.store, self.vehicle, self.procedure)
            def reassign_after_read(*_args):
                self.store.db.execute("UPDATE procedures SET vehicle_id=? WHERE id=?",
                                      (self.foreign, self.procedure))
                self.store.db.commit()
                return original
            before_children = tuple(window.winfo_children())
            with (patch("repair_procedures_gui.warning_overview_text",
                        side_effect=reassign_after_read),
                  patch("tkinter.messagebox.showerror") as error):
                self.assertIsNone(window.open_warning_overview())
            error.assert_called_once()
            self.assertEqual(tuple(window.winfo_children()), before_children)
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()
