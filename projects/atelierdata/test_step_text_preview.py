"""Synthetic step-linked TXT preview tests; no proprietary service data."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from atelierdata import Store
from document_library import import_local_file, set_metadata
from procedure_audit import read_step_text_preview
from repair_procedures import add_step, create_procedure, update_step


class StepTextPreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.store = Store(self.folder / "workshop.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("TEST", "CAR", "SYNTHETIC", "2026")
        self.other_vehicle = self.store.add_vehicle("OTHER", "CAR")
        source = self.folder / "authorized.txt"
        source.write_text("OWNED SYNTHETIC DOCUMENT\nWarning: fictional only.", encoding="utf-8")
        self.attachment = import_local_file(
            self.store, self.vehicle, source, "Manual de atelier",
            "Synthetic note", "User-owned fixture", rights_basis="document_propriu")
        self.article = self.store.db.execute(
            "SELECT article_id FROM attachments WHERE id=?", (self.attachment,)
        ).fetchone()[0]
        self.procedure = create_procedure(
            self.store, self.vehicle, "SYNTHETIC", "Test procedure",
            source="User-authored fixture")
        self.step = add_step(
            self.store, self.procedure, "Fictional instruction",
            safety_note="Fictional warning", article_id=self.article)
        self.other_article = self.store.add_article(
            self.vehicle, "Note atelier", "Unrelated", "", "User-owned fixture")
        self.foreign_article = self.store.add_article(
            self.other_vehicle, "Note atelier", "Foreign", "", "Other source")

    def preview(self, **kwargs):
        args = dict(step_id=self.step, vehicle_id=self.vehicle,
                    procedure_id=self.procedure, attachment_id=self.attachment)
        args.update(kwargs)
        return read_step_text_preview(self.store, **args)

    def test_authorized_text_preview_is_read_only(self):
        before = self.store.db.total_changes
        self.assertIn("OWNED SYNTHETIC DOCUMENT", self.preview())
        self.assertEqual(self.store.db.total_changes, before)

    def test_revoked_rights_block_step_preview(self):
        set_metadata(self.store, self.attachment, "Manual de atelier",
                     "Synthetic note", "User-owned fixture",
                     rights_basis="neconfirmat")
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "Drepturi neconfirmate"):
            self.preview()
        self.assertEqual(self.store.db.total_changes, before)

    def test_relinked_or_cross_vehicle_step_blocks_stale_attachment(self):
        for replacement in (self.other_article, self.foreign_article, None):
            with self.subTest(article=replacement):
                if replacement == self.foreign_article:
                    # The public API correctly rejects foreign links; simulate
                    # a damaged/imported SQLite row to test the read boundary.
                    self.store.db.execute(
                        "UPDATE procedure_steps SET article_id=? WHERE id=?",
                        (replacement, self.step))
                    self.store.db.commit()
                else:
                    update_step(self.store, self.step, "Fictional instruction",
                                "Fictional warning", replacement)
                before = self.store.db.total_changes
                with self.assertRaises(ValueError):
                    self.preview()
                self.assertEqual(self.store.db.total_changes, before)

    def test_reassigned_attachment_blocks_step_preview(self):
        self.store.db.execute(
            "UPDATE attachments SET article_id=? WHERE id=?",
            (self.other_article, self.attachment))
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError, "nu mai aparține"):
            self.preview()

    def test_invalid_ids_do_not_coerce_sqlite(self):
        before = self.store.db.total_changes
        for invalid in (True, 1.0, "1", None, -1, 0):
            with self.subTest(invalid=repr(invalid)):
                for key in ("step_id", "vehicle_id", "procedure_id", "attachment_id"):
                    with self.assertRaises(ValueError):
                        self.preview(**{key: invalid})
        self.assertEqual(self.store.db.total_changes, before)

    def test_change_during_read_invalidates_preview(self):
        from document_library import read_verified_text_preview
        def relink(*args, **kwargs):
            value = read_verified_text_preview(*args, **kwargs)
            update_step(self.store, self.step, "Fictional instruction",
                        "Fictional warning", self.other_article)
            return value
        with patch("document_library.read_verified_text_preview", side_effect=relink):
            with self.assertRaisesRegex(ValueError, "modificat"):
                self.preview()

    def test_gui_opens_internal_preview_and_rejects_revocation(self):
        from repair_procedures_gui import open_procedures_window
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
        window.update_idletasks()
        window.steps_tree.selection_set(str(self.step))
        popup = window.open_step_reference()
        self.assertIsNotNone(popup)
        self.addCleanup(popup.destroy)
        before = self.store.db.total_changes
        preview = popup.preview_attachment(self.attachment)
        self.assertIsNotNone(preview)
        self.addCleanup(preview.destroy)
        self.assertEqual(preview.preview_text_widget.cget("state"), "disabled")
        self.assertIn("OWNED SYNTHETIC DOCUMENT",
                      preview.preview_text_widget.get("1.0", "end"))
        self.assertEqual(self.store.db.total_changes, before)
        set_metadata(self.store, self.attachment, "Manual de atelier",
                     "Synthetic note", "User-owned fixture",
                     rights_basis="neconfirmat")
        before = self.store.db.total_changes
        with patch("tkinter.messagebox.showerror") as error:
            self.assertIsNone(popup.preview_attachment(self.attachment))
            self.assertTrue(error.called)
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
