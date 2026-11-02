"""Synthetic SQLite and Tkinter tests for warning-to-document navigation."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from atelierdata import Store
from procedure_warning_reference import warning_step_reference_id
from repair_procedures import create_procedure, add_step, update_step
from repair_procedures_gui import open_procedures_window


class WarningDocumentNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "warnings-document.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "A")
        self.foreign_vehicle = self.store.add_vehicle("SYNTHETIC", "B")
        self.document = self.store.add_article(
            self.vehicle, "Documentație", "Original test document",
            "Synthetic test content", "USER-OWNED TEST SOURCE")
        self.second_document = self.store.add_article(
            self.vehicle, "Documentație", "Changed test document",
            "Synthetic replacement", "USER-OWNED TEST SOURCE")
        self.foreign_document = self.store.add_article(
            self.foreign_vehicle, "Documentație", "PRIVATE OTHER VEHICLE",
            "Foreign fixture", "PRIVATE TEST SOURCE")
        self.procedure = create_procedure(
            self.store, self.vehicle, "TEST", "Synthetic procedure",
            source="USER-OWNED TEST SOURCE")
        self.first = add_step(
            self.store, self.procedure, "Synthetic instruction",
            safety_note="Recorded synthetic warning", article_id=self.document)
        self.no_document = add_step(
            self.store, self.procedure, "Synthetic second instruction",
            safety_note="Second warning")
        self.no_warning = add_step(
            self.store, self.procedure, "Synthetic third instruction",
            article_id=self.document)

    def resolve(self, step=None):
        return warning_step_reference_id(
            self.store, self.vehicle, self.procedure,
            self.first if step is None else step)

    def test_same_vehicle_document_and_warning_are_read_only(self):
        before = self.store.db.total_changes
        self.assertEqual(
            self.resolve(), (self.document, "Recorded synthetic warning"))
        self.assertEqual(self.store.db.total_changes, before)

    def test_missing_document_warning_and_invalid_identifiers(self):
        before = self.store.db.total_changes
        for step in (self.no_document, self.no_warning, 999999):
            with self.subTest(step=step), self.assertRaises(ValueError):
                self.resolve(step)
        for name in ("vehicle_id", "procedure_id", "step_id"):
            for bad in (True, False, "1", 1.0, 0, -1):
                args = dict(vehicle_id=self.vehicle, procedure_id=self.procedure,
                            step_id=self.first)
                args[name] = bad
                with self.subTest(name=name, bad=repr(bad)):
                    with self.assertRaises(ValueError):
                        warning_step_reference_id(self.store, **args)
        self.assertEqual(self.store.db.total_changes, before)

    def test_foreign_document_and_reassigned_procedure_are_rejected(self):
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.foreign_document, self.first))
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError, "another vehicle"):
            self.resolve()
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.document, self.first))
        self.store.db.execute(
            "UPDATE procedures SET vehicle_id=? WHERE id=?",
            (self.foreign_vehicle, self.procedure))
        self.store.db.commit()
        with self.assertRaises(ValueError):
            self.resolve()

    def test_live_changes_to_warning_or_document(self):
        update_step(self.store, self.first, "Synthetic instruction",
                    "Recorded synthetic warning", self.second_document)
        self.assertEqual(self.resolve()[0], self.second_document)
        update_step(self.store, self.first, "Synthetic instruction", "",
                    self.second_document)
        with self.assertRaisesRegex(ValueError, "no longer has"):
            self.resolve()
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

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
        popup.warning_steps.selection_set(str(self.first))
        return window, popup

    def test_gui_opens_current_document_from_warning_without_writes(self):
        window, popup = self.open_window()
        before = self.store.db.total_changes
        document_popup = popup.open_warning_reference()
        self.assertIsNotNone(document_popup)
        self.addCleanup(lambda: document_popup.winfo_exists() and document_popup.destroy())
        self.assertEqual(document_popup.reference_article_id, self.document)
        self.assertIn("USER-OWNED TEST SOURCE",
                      document_popup.reference_text_widget.get("1.0", "end"))
        self.assertEqual(window.steps_tree.selection(), (str(self.first),))
        self.assertEqual(self.store.db.total_changes, before)

    def test_gui_rejects_changed_warning_without_showing_stale_document(self):
        window, popup = self.open_window()
        self.store.db.execute(
            "UPDATE procedure_steps SET safety_note=? WHERE id=?",
            ("Updated warning", self.first))
        self.store.db.commit()
        before = self.store.db.total_changes
        with patch("tkinter.messagebox.showinfo") as info:
            self.assertIsNone(popup.open_warning_reference())
        info.assert_called_once()
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(popup.warning_steps.item(str(self.first), "values")[1],
                         "Updated warning")

    def test_gui_rejects_corrupt_cross_vehicle_document_link(self):
        window, popup = self.open_window()
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.foreign_document, self.first))
        self.store.db.commit()
        before = self.store.db.total_changes
        with patch("tkinter.messagebox.showinfo") as info:
            self.assertIsNone(popup.open_warning_reference())
        info.assert_called_once()
        self.assertEqual(self.store.db.total_changes, before)
        self.assertNotIn("PRIVATE OTHER VEHICLE",
                         window.procedure_detail_text.get("1.0", "end"))

    def test_gui_rejects_link_changed_during_document_snapshot(self):
        window, popup = self.open_window()
        from repair_procedures_gui import get_step_reference_snapshot
        original = get_step_reference_snapshot

        def relink_during_snapshot(*args, **kwargs):
            update_step(self.store, self.first, "Synthetic instruction",
                        "Recorded synthetic warning", self.second_document)
            return original(*args, **kwargs)

        with patch("repair_procedures_gui.get_step_reference_snapshot",
                   side_effect=relink_during_snapshot):
            with patch("tkinter.messagebox.showerror") as error:
                self.assertIsNone(popup.open_warning_reference())
        error.assert_called_once()
        self.assertEqual(
            self.store.db.execute(
                "SELECT article_id FROM procedure_steps WHERE id=?",
                (self.first,)).fetchone()[0], self.second_document)


    def test_gui_rejects_warning_revoked_during_document_snapshot(self):
        window, popup = self.open_window()
        from repair_procedures_gui import get_step_reference_snapshot
        original = get_step_reference_snapshot

        def revoke_after_snapshot(*args, **kwargs):
            snapshot = original(*args, **kwargs)
            self.store.db.execute(
                "UPDATE procedure_steps SET safety_note='' WHERE id=?",
                (self.first,))
            self.store.db.commit()
            return snapshot

        before = self.store.db.total_changes
        with patch("repair_procedures_gui.get_step_reference_snapshot",
                   side_effect=revoke_after_snapshot):
            with patch("tkinter.messagebox.showerror") as error:
                self.assertIsNone(popup.open_warning_reference())
        error.assert_called_once()
        self.assertEqual(self.store.db.total_changes, before + 1)
        self.assertEqual(self.store.db.execute(
            "SELECT safety_note FROM procedure_steps WHERE id=?",
            (self.first,)).fetchone()[0], "")

    def test_gui_rejects_selection_changed_during_document_snapshot(self):
        window, popup = self.open_window()
        from repair_procedures_gui import get_step_reference_snapshot
        original = get_step_reference_snapshot

        def change_selection_after_snapshot(*args, **kwargs):
            snapshot = original(*args, **kwargs)
            window.steps_tree.selection_set(str(self.no_document))
            return snapshot

        before = self.store.db.total_changes
        with patch("repair_procedures_gui.get_step_reference_snapshot",
                   side_effect=change_selection_after_snapshot):
            with patch("tkinter.messagebox.showerror") as error:
                self.assertIsNone(popup.open_warning_reference())
        error.assert_called_once()
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
