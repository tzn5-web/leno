"""Synthetic document-reference regression tests for the Windows search dialog."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from atelierdata import Store
from repair_procedures import add_step, create_procedure
from procedure_search_hits import list_procedure_hits
from procedure_search_live import validate_live_hit
from repair_procedures_gui import open_procedures_window


class DocumentReferenceNavigationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "document-navigation.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "A")
        self.other_vehicle = self.store.add_vehicle("SYNTHETIC", "B")
        self.article = self.store.add_article(
            self.vehicle, "Diagram", "SCHEMATIC-KEY", "CONTENT-KEY", "OWNED")
        self.other_article = self.store.add_article(
            self.other_vehicle, "Diagram", "SCHEMATIC-KEY", "CONTENT-KEY", "OWNED")
        self.procedure = create_procedure(
            self.store, self.vehicle, "TEST", "Reference test", source="OWNED")
        self.step = add_step(
            self.store, self.procedure, "Review owned diagram", article_id=self.article)

    def test_document_body_change_invalidates_content_hit(self):
        hit = next(h for h in list_procedure_hits(
            self.store, self.vehicle, "CONTENT-KEY")
            if h["field"] == "Conținut document")
        self.assertTrue(validate_live_hit(self.store, self.vehicle, hit, "CONTENT-KEY"))
        self.store.db.execute(
            "UPDATE articles SET content=? WHERE id=?", ("REPLACED", self.article))
        self.store.db.commit()
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "changed"):
            validate_live_hit(self.store, self.vehicle, hit, "CONTENT-KEY")
        self.assertEqual(self.store.db.total_changes, before)

    def test_document_relink_to_foreign_vehicle_never_validates(self):
        hit = next(h for h in list_procedure_hits(
            self.store, self.vehicle, "SCHEMATIC-KEY")
            if h["field"] == "Titlu document")
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.other_article, self.step))
        self.store.db.commit()
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle, hit, "SCHEMATIC-KEY")

    def test_tk_dialog_rejects_stale_document_before_navigation(self):
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
        window.procedure_search_var.set("SCHEMATIC-KEY")
        popup = window.open_search_hits()
        self.assertIsNotNone(popup)
        self.addCleanup(lambda: popup.winfo_exists() and popup.destroy())
        popup.hits_tree.selection_set("0")
        self.store.db.execute(
            "UPDATE articles SET title=? WHERE id=?", ("REPLACED", self.article))
        self.store.db.commit()
        with patch("tkinter.messagebox.showerror") as error:
            self.assertIsNone(popup.go_to_hit())
        error.assert_called_once()
        self.assertNotEqual(window.steps_tree.selection(), (str(self.step),))


if __name__ == "__main__":
    unittest.main()
