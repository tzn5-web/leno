"""Synthetic SQLite and Tk regression tests for live step-document popups."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from atelierdata import Store
from atelierdata_extensions import attach_document, list_documents
from procedure_audit import get_step_reference_snapshot
from repair_procedures import add_step, create_procedure
from repair_procedures_gui import open_procedures_window


class StepReferenceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        folder = Path(self.tmp.name)
        self.store = Store(folder / "fixture.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "CAR")
        self.other_vehicle = self.store.add_vehicle("OTHER", "CAR")
        self.procedure = create_procedure(
            self.store, self.vehicle, "TEST", "Inert procedure",
            source="USER-OWNED SYNTHETIC FIXTURE")
        self.article = self.store.add_article(
            self.vehicle, "Synthetic", "Fixture title",
            "Inert text", "USER-OWNED SYNTHETIC FIXTURE")
        self.alternative = self.store.add_article(
            self.vehicle, "Synthetic", "Other fixture",
            "Other inert text", "USER-OWNED SYNTHETIC FIXTURE")
        self.step = add_step(self.store, self.procedure, "Inert step",
                             article_id=self.article)
        fixture = folder / "inert.txt"
        fixture.write_text("Synthetic, no repair specifications", encoding="utf-8")
        self.attachment = attach_document(self.store, self.article, fixture)

    def snapshot(self):
        return get_step_reference_snapshot(
            self.store, self.step, self.vehicle, self.procedure)

    def test_live_snapshot_contains_only_linked_article_and_attachment_without_writes(self):
        before = self.store.db.total_changes
        article, attachments = self.snapshot()
        self.assertEqual(article["id"], self.article)
        self.assertEqual(tuple(row["id"] for row in attachments), (self.attachment,))
        self.assertEqual(self.store.db.total_changes, before)

    def test_step_relinked_during_attachment_fetch_is_rejected(self):
        def mutate(store, article_id):
            rows = list_documents(store, article_id)
            store.db.execute("UPDATE procedure_steps SET article_id=? WHERE id=?",
                             (self.alternative, self.step))
            store.db.commit()
            return rows
        with patch("procedure_audit.list_documents", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "modificat"):
                self.snapshot()

    def test_article_metadata_changed_during_fetch_is_rejected(self):
        def mutate(store, article_id):
            rows = list_documents(store, article_id)
            store.db.execute("UPDATE articles SET content=? WHERE id=?",
                             ("Changed content", self.article))
            store.db.commit()
            return rows
        with patch("procedure_audit.list_documents", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "modificat"):
                self.snapshot()

    def test_attachment_reassigned_during_fetch_is_rejected(self):
        def mutate(store, article_id):
            rows = list_documents(store, article_id)
            store.db.execute("UPDATE attachments SET article_id=? WHERE id=?",
                             (self.alternative, self.attachment))
            store.db.commit()
            return rows
        with patch("procedure_audit.list_documents", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "Atașamentele"):
                self.snapshot()

    def test_attachment_path_changed_during_fetch_is_rejected(self):
        def mutate(store, article_id):
            rows = list_documents(store, article_id)
            store.db.execute("UPDATE attachments SET path=? WHERE id=?",
                             ("changed.txt", self.attachment))
            store.db.commit()
            return rows
        with patch("procedure_audit.list_documents", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "Atașamentele"):
                self.snapshot()

    def test_foreign_vehicle_and_invalid_identifiers_are_rejected(self):
        for bad in (True, False, 1.0, "1", 0, -1):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):
                    get_step_reference_snapshot(
                        self.store, bad, self.vehicle, self.procedure)
        with self.assertRaises(ValueError):
            get_step_reference_snapshot(
                self.store, self.step, self.other_vehicle, self.procedure)

    def test_tk_document_popup_rejects_relink_during_fetch(self):
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
        try:
            window.steps_tree.selection_set(str(self.step))
            before_children = tuple(window.winfo_children())
            def mutate(store, article_id):
                rows = list_documents(store, article_id)
                store.db.execute("UPDATE procedure_steps SET article_id=? WHERE id=?",
                                 (self.alternative, self.step))
                store.db.commit()
                return rows
            with (patch("procedure_audit.list_documents", side_effect=mutate),
                  patch("tkinter.messagebox.showerror") as error):
                window.open_step_reference()
            error.assert_called_once()
            self.assertEqual(tuple(window.winfo_children()), before_children)
            self.assertNotIn("Other inert text",
                window.procedure_detail_text.get("1.0", "end"))
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()
