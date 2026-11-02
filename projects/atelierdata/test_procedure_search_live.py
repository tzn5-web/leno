"""Synthetic SQLite and Tkinter regressions for stale search-result navigation."""
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


class LiveSearchHitTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "live-search.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "A")
        self.foreign = self.store.add_vehicle("SYNTHETIC", "B")
        self.document = self.store.add_article(
            self.vehicle, "Notes", "DOC-KEY reference", "Synthetic body", "OWNED-SOURCE")
        self.foreign_doc = self.store.add_article(
            self.foreign, "Notes", "FOREIGN-SECRET", "Foreign body", "OTHER-SOURCE")
        self.pid = create_procedure(
            self.store, self.vehicle, "TEST", "Procedure", source="OWNED-SOURCE")
        self.sid = add_step(self.store, self.pid, "Synthetic instruction",
                            safety_note="WARNING-KEY", article_id=self.document)

    def hit(self, search, field):
        return next(h for h in list_procedure_hits(self.store, self.vehicle, search)
                    if h["field"] == field)

    def test_live_warning_and_document_hits_are_read_only(self):
        before = self.store.db.total_changes
        self.assertTrue(validate_live_hit(
            self.store, self.vehicle, self.hit("WARNING-KEY", "Avertisment pas"),
            "WARNING-KEY"))
        self.assertTrue(validate_live_hit(
            self.store, self.vehicle, self.hit("DOC-KEY", "Titlu document"), "DOC-KEY"))
        self.assertEqual(self.store.db.total_changes, before)

    def test_reject_changed_warning_and_deleted_step(self):
        hit = self.hit("WARNING-KEY", "Avertisment pas")
        self.store.db.execute(
            "UPDATE procedure_steps SET safety_note='REPLACED' WHERE id=?", (self.sid,))
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError, "changed"):
            validate_live_hit(self.store, self.vehicle, hit, "WARNING-KEY")
        self.store.db.execute("DELETE FROM procedure_steps WHERE id=?", (self.sid,))
        self.store.db.commit()
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle, hit, "WARNING-KEY")

    def test_reject_relinked_and_cross_vehicle_documents(self):
        hit = self.hit("DOC-KEY", "Titlu document")
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?", (self.foreign_doc, self.sid))
        self.store.db.commit()
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle, hit, "DOC-KEY")
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_reject_reassigned_procedure_and_bad_ids(self):
        hit = self.hit("WARNING-KEY", "Avertisment pas")
        for invalid in (True, 1.0, "1", None, 0):
            with self.subTest(value=repr(invalid)), self.assertRaises(ValueError):
                validate_live_hit(self.store, invalid, hit, "WARNING-KEY")
        self.store.db.execute(
            "UPDATE procedures SET vehicle_id=? WHERE id=?", (self.foreign, self.pid))
        self.store.db.commit()
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle, hit, "WARNING-KEY")

    def test_reject_invalid_field_and_metadata_step_mix(self):
        hit = self.hit("WARNING-KEY", "Avertisment pas")
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle, {**hit, "field": "DROP TABLE"}, "WARNING-KEY")
        metadata = self.hit("OWNED-SOURCE", "Proveniență procedură")
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle, {**metadata, "step_id": self.sid},
                              "OWNED-SOURCE")

    def open_gui(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.vehicle)
        window = open_procedures_window(app, object, selected_procedure_id=self.pid)
        self.addCleanup(lambda: window.winfo_exists() and window.destroy())
        window.procedure_search_var.set("WARNING-KEY")
        popup = window.open_search_hits()
        self.assertIsNotNone(popup)
        self.addCleanup(lambda: popup.winfo_exists() and popup.destroy())
        popup.hits_tree.selection_set("0")
        return window, popup

    def test_tk_rejects_stale_warning_before_navigation(self):
        window, popup = self.open_gui()
        self.store.db.execute(
            "UPDATE procedure_steps SET safety_note='REMOVED' WHERE id=?", (self.sid,))
        self.store.db.commit()
        with patch("tkinter.messagebox.showerror") as error:
            self.assertIsNone(popup.go_to_hit())
        error.assert_called_once()
        self.assertNotEqual(window.steps_tree.selection(), (str(self.sid),))

    def test_tk_navigates_current_warning_without_writes(self):
        window, popup = self.open_gui()
        before = self.store.db.total_changes
        result = popup.go_to_hit()
        self.assertEqual(result["step_id"], self.sid)
        self.assertEqual(window.steps_tree.selection(), (str(self.sid),))
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
