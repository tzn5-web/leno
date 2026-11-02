"""Synthetic read-only context and Tkinter integration tests for selected repair steps."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from atelierdata import Store
from procedure_step_context import step_context_text
from repair_procedures import (add_step, create_procedure, delete_step,
                               move_step, update_step)
from repair_procedures_gui import open_procedures_window


class SelectedStepContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "context.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "CAR")
        self.other = self.store.add_vehicle("FOREIGN", "CAR")
        self.procedure = create_procedure(
            self.store, self.vehicle, "TEST SYSTEM", "Synthetic procedure",
            precautions="Synthetic general caution", source="USER-OWNED FIXTURE")
        self.document = self.store.add_article(
            self.vehicle, "Synthetic", "Authorized fixture", "Inert test",
            "LICENSED TEST SOURCE")
        self.foreign = self.store.add_article(
            self.other, "Synthetic", "PRIVATE OTHER VEHICLE", "Inert test",
            "FOREIGN SOURCE")
        self.first = add_step(
            self.store, self.procedure, "Synthetic first instruction",
            safety_note="Synthetic step warning", article_id=self.document)
        self.second = add_step(self.store, self.procedure, "Synthetic second instruction")

    def context(self, step=None, vehicle=None, procedure=None):
        return step_context_text(
            self.store,
            self.vehicle if vehicle is None else vehicle,
            self.procedure if procedure is None else procedure,
            self.first if step is None else step)

    def test_selected_step_displays_warning_document_and_sources_without_writes(self):
        before = self.store.db.total_changes
        result = self.context()
        for expected in ("PAS 1:", "Synthetic first instruction",
                         "AVERTISMENT GENERAL: Synthetic general caution",
                         "ATENȚIE LA ACEST PAS: Synthetic step warning",
                         "DOCUMENT ASOCIAT: Authorized fixture",
                         "SURSĂ DOCUMENT: LICENSED TEST SOURCE",
                         "SURSĂ PROCEDURĂ: USER-OWNED FIXTURE"):
            self.assertIn(expected, result)
        self.assertNotIn("Synthetic second instruction", result)
        self.assertEqual(self.store.db.total_changes, before)

    def test_corrupt_cross_vehicle_reference_hides_foreign_metadata(self):
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.foreign, self.first))
        self.store.db.commit()
        before = self.store.db.total_changes
        result = self.context()
        self.assertIn("AVERTISMENT REFERINȚĂ", result)
        self.assertNotIn("PRIVATE OTHER VEHICLE", result)
        self.assertNotIn("FOREIGN SOURCE", result)
        self.assertNotIn("DOCUMENT ASOCIAT:", result)
        self.assertEqual(self.store.db.total_changes, before)

    def test_deleted_foreign_and_invalid_ids_are_rejected(self):
        before = self.store.db.total_changes
        for bad in (True, False, 1.0, "1", 0, -1):
            for name in ("vehicle_id", "procedure_id", "step_id"):
                args = dict(vehicle_id=self.vehicle, procedure_id=self.procedure,
                            step_id=self.first)
                args[name] = bad
                with self.subTest(name=name, bad=repr(bad)):
                    with self.assertRaises(ValueError):
                        step_context_text(self.store, **args)
        with self.assertRaises(ValueError):
            self.context(vehicle=self.other)
        with self.assertRaises(ValueError):
            self.context(step=999999)
        self.assertEqual(self.store.db.total_changes, before)
        delete_step(self.store, self.first)
        with self.assertRaises(ValueError):
            self.context()

    def test_reordering_and_relinking_are_read_live(self):
        self.assertIn("PAS 1:", self.context())
        move_step(self.store, self.first, 1)
        self.assertIn("PAS 2:", self.context())
        update_step(self.store, self.first, "Changed synthetic instruction",
                    article_id=None)
        result = self.context()
        self.assertIn("Changed synthetic instruction", result)
        self.assertNotIn("DOCUMENT ASOCIAT:", result)
        self.assertNotIn("Synthetic step warning", result)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_tk_selection_updates_context_and_rejects_stale_step(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.vehicle)
        window = open_procedures_window(
            app, object, selected_procedure_id=self.procedure,
            selected_step_id=self.first)
        try:
            window.update_idletasks()
            first = window.render_selected_step()
            self.assertIn("Synthetic step warning", first)
            self.assertIn("Authorized fixture", first)
            window.steps_tree.selection_set(str(self.second))
            second = window.render_selected_step()
            self.assertIn("Synthetic second instruction", second)
            self.assertNotIn("Authorized fixture", second)
            window.steps_tree.selection_set(str(self.first))
            self.store.db.execute(
                "UPDATE procedure_steps SET article_id=? WHERE id=?",
                (self.foreign, self.first))
            self.store.db.commit()
            self.assertIn("AVERTISMENT REFERINȚĂ", window.render_selected_step())
            delete_step(self.store, self.first)
            self.assertIsNone(window.render_selected_step())
            text = window.procedure_detail_text.get("1.0", "end")
            self.assertIn("nu mai aparține", text)
            self.assertNotIn("PRIVATE OTHER VEHICLE", text)
        finally:
            window.destroy()


    def test_tk_reassigned_procedure_clears_foreign_context_and_rows(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.vehicle)
        window = open_procedures_window(
            app, object, selected_procedure_id=self.procedure,
            selected_step_id=self.first)
        try:
            self.assertIn("Synthetic first instruction", window.render_selected_step())
            self.store.db.execute(
                "UPDATE procedures SET vehicle_id=? WHERE id=?",
                (self.other, self.procedure))
            self.store.db.commit()
            before = self.store.db.total_changes
            self.assertIsNone(window.render_selected_step())
            self.assertEqual(window.steps_tree.get_children(), ())
            self.assertFalse(window.procedures_tree.exists(str(self.procedure)))
            text = window.procedure_detail_text.get("1.0", "end")
            self.assertIn("nu mai aparține", text)
            self.assertNotIn("Synthetic first instruction", text)
            self.assertNotIn("Authorized fixture", text)
            self.assertEqual(self.store.db.total_changes, before)
        finally:
            window.destroy()

    def test_tk_reassigned_procedure_blocks_step_mutation(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.vehicle)
        window = open_procedures_window(
            app, object, selected_procedure_id=self.procedure,
            selected_step_id=self.first)
        try:
            self.store.db.execute(
                "UPDATE procedures SET vehicle_id=? WHERE id=?",
                (self.other, self.procedure))
            self.store.db.commit()
            before = self.store.db.total_changes
            with patch("tkinter.messagebox.showerror") as error:
                self.assertIsNone(window.move_selected_step(1))
            error.assert_called_once()
            self.assertEqual(self.store.db.total_changes, before)
            self.assertEqual(
                self.store.db.execute(
                    "SELECT step_number FROM procedure_steps WHERE id=?",
                    (self.first,)).fetchone()[0], 1)
            self.assertEqual(window.steps_tree.get_children(), ())
        finally:
            window.destroy()



if __name__ == "__main__":
    unittest.main()
