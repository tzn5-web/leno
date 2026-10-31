"""Tkinter regression: schematic filters must revoke stale preview state.

Uses only generated images and synthetic, user-owned SQLite records.
"""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from atelierdata import Store
from atelierdata_extensions import attach_document
from schematic_viewer import open_schematics_window


class SchematicGuiSearchStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.store = Store(self.folder / "test.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "TEST")
        self.article = self.store.add_article(
            self.vehicle, "Scheme electrice", "Straße synthetic",
            "Owner-authored diagram", "TEST OWNER")
        image_path = self.folder / "owner.png"
        Image.new("RGB", (32, 16), (12, 34, 56)).save(image_path)
        self.attachment = attach_document(self.store, self.article, image_path)
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("No graphical Tk display: " + str(exc))
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        app = SimpleNamespace(
            tk=tk, root=self.root, db=self.store, vid=self.vehicle,
            refresh=lambda: None)
        self.viewer = open_schematics_window(
            app, object, selected_article_id=self.article)
        self.addCleanup(self.viewer.destroy)
        self.root.update()

    def assert_preview_present(self):
        self.assertEqual(self.viewer.schematics_tree.selection(),
                         (str(self.article),))
        self.assertEqual(self.viewer.attachments_tree.get_children(),
                         (str(self.attachment),))
        self.assertEqual(len(self.viewer.diagram_canvas.find_all()), 1)
        self.assertIn("Owner-authored diagram",
                      self.viewer.schematic_details_text.get("1.0", "end"))

    def assert_preview_cleared(self):
        self.assertEqual(self.viewer.attachments_tree.get_children(), ())
        self.assertEqual(self.viewer.diagram_canvas.find_all(), ())
        self.assertFalse(self.viewer.schematic_details_text.get("1.0", "end").strip())

    def test_filter_excluding_selected_article_revokes_preview(self):
        before = self.store.db.total_changes
        self.assert_preview_present()
        self.viewer.schematic_search_var.set("STRASSE")
        self.root.update()
        self.assert_preview_present()
        self.viewer.schematic_search_var.set("no matching synthetic diagram")
        self.root.update()
        self.assertEqual(self.viewer.schematics_tree.get_children(), ())
        self.assert_preview_cleared()
        self.assertEqual(self.viewer.schematic_title_var.get(), "Selectează o schemă")
        self.viewer.schematic_search_var.set("")
        self.root.update()
        self.assertTrue(self.viewer.schematics_tree.exists(str(self.article)))
        self.assert_preview_cleared()
        self.viewer.schematics_tree.selection_set(str(self.article))
        self.root.update()
        self.assert_preview_present()
        self.assertEqual(self.store.db.total_changes, before)

    def test_invalid_search_revokes_preview_and_shows_error(self):
        before = self.store.db.total_changes
        self.assert_preview_present()
        self.viewer.schematic_search_var.set("x" * 201)
        self.root.update()
        self.assertEqual(self.viewer.schematics_tree.get_children(), ())
        self.assert_preview_cleared()
        self.assertIn("invalidă", self.viewer.schematic_title_var.get())
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
