"""Synthetic SQLite and Tkinter tests for live procedure-to-schematic navigation."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from atelierdata import Store
from procedure_schematic_link import linked_step_schematic_id
from repair_procedures import add_step, create_procedure
from repair_procedures_gui import open_procedures_window


class LiveSchematicLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "schematic_link.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "CAR")
        self.other = self.store.add_vehicle("FOREIGN", "CAR")
        self.schematic = self.store.add_article(
            self.vehicle, "Scheme electrice", "Fixture diagram", "Inert",
            "USER-OWNED FIXTURE")
        self.second = self.store.add_article(
            self.vehicle, "Siguranțe și relee", "Fixture fuse diagram", "Inert",
            "USER-OWNED FIXTURE")
        self.note = self.store.add_article(
            self.vehicle, "Note atelier", "Not a diagram", "Inert",
            "USER-OWNED FIXTURE")
        self.foreign = self.store.add_article(
            self.other, "Scheme electrice", "FOREIGN DIAGRAM", "Inert",
            "FOREIGN FIXTURE")
        self.procedure = create_procedure(
            self.store, self.vehicle, "TEST", "Synthetic procedure",
            source="USER-OWNED FIXTURE")
        self.step = add_step(self.store, self.procedure, "Inert instruction",
                             article_id=self.schematic)

    def resolve(self, **changes):
        ids = dict(vehicle_id=self.vehicle, procedure_id=self.procedure,
                   step_id=self.step)
        ids.update(changes)
        return linked_step_schematic_id(self.store, **ids)

    def test_valid_link_and_updates_are_read_only(self):
        before = self.store.db.total_changes
        self.assertEqual(self.resolve(), self.schematic)
        self.assertEqual(self.store.db.total_changes, before)
        self.store.db.execute("UPDATE procedure_steps SET article_id=? WHERE id=?",
                              (self.second, self.step))
        self.store.db.commit()
        self.assertEqual(self.resolve(), self.second)

    def test_reject_untyped_and_foreign_identifiers(self):
        before = self.store.db.total_changes
        for key in ("vehicle_id", "procedure_id", "step_id"):
            for bad in (True, False, 1.0, "1", 0, -1):
                with self.subTest(key=key, bad=repr(bad)):
                    with self.assertRaises(ValueError):
                        self.resolve(**{key: bad})
        with self.assertRaises(ValueError):
            self.resolve(vehicle_id=self.other)
        with self.assertRaises(ValueError):
            self.resolve(step_id=999999)
        self.assertEqual(self.store.db.total_changes, before)

    def test_invalid_category_and_cross_vehicle_links_hide_metadata(self):
        for article in (self.note, self.foreign, None):
            with self.subTest(article=article):
                self.store.db.execute(
                    "UPDATE procedure_steps SET article_id=? WHERE id=?",
                    (article, self.step))
                self.store.db.commit()
                with self.assertRaises(ValueError) as error:
                    self.resolve()
                self.assertNotIn("FOREIGN DIAGRAM", str(error.exception))

    def test_procedure_reassignment_and_step_reassignment_rejected(self):
        self.store.db.execute("UPDATE procedures SET vehicle_id=? WHERE id=?",
                              (self.other, self.procedure))
        self.store.db.commit()
        with self.assertRaises(ValueError):
            self.resolve()
        self.store.db.execute("UPDATE procedures SET vehicle_id=? WHERE id=?",
                              (self.vehicle, self.procedure))
        other_procedure = create_procedure(
            self.store, self.vehicle, "TEST", "Other procedure",
            source="USER-OWNED FIXTURE")
        self.store.db.execute("UPDATE procedure_steps SET procedure_id=? WHERE id=?",
                              (other_procedure, self.step))
        self.store.db.commit()
        with self.assertRaises(ValueError):
            self.resolve()
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def _window(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.vehicle)
        window = open_procedures_window(
            app, object, selected_procedure_id=self.procedure,
            selected_step_id=self.step)
        self.addCleanup(window.destroy)
        # Set the selection explicitly; do not depend on deferred Tk events.
        window.steps_tree.selection_set(str(self.step))
        return window

    def test_tk_opens_verified_current_schematic(self):
        window = self._window()
        sentinel = object()
        with (patch("schematic_viewer.open_schematics_window",
                    return_value=sentinel) as opened,
              patch("tkinter.messagebox.showinfo") as info):
            self.assertIs(window.open_schematic_reference(), sentinel)
        info.assert_not_called()
        opened.assert_called_once()
        self.assertEqual(opened.call_args.kwargs["selected_article_id"],
                         self.schematic)
        self.assertEqual(opened.call_args.kwargs["vehicle_id"], self.vehicle)

    def test_tk_rejects_link_changed_during_validation(self):
        window = self._window()
        from schematic_viewer import get_schematic_reference
        def relink_after_validation(store, vehicle_id, article_id):
            result = get_schematic_reference(store, vehicle_id, article_id)
            self.store.db.execute(
                "UPDATE procedure_steps SET article_id=? WHERE id=?",
                (self.second, self.step))
            self.store.db.commit()
            return result
        with (patch("schematic_viewer.get_schematic_reference",
                    side_effect=relink_after_validation),
              patch("schematic_viewer.open_schematics_window") as opened,
              patch("tkinter.messagebox.showinfo") as info):
            self.assertIsNone(window.open_schematic_reference())
        opened.assert_not_called()
        info.assert_called_once()
        self.assertEqual(self.resolve(), self.second)


if __name__ == "__main__":
    unittest.main()
