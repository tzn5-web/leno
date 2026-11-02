"""Synthetic, authorized PDF previews from current repair-procedure steps."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from atelierdata import Store
from document_library import import_local_file, set_metadata
from repair_procedures import add_step, create_procedure, update_step
from step_pdf_preview import read_step_pdf_page
from test_document_pdf_preview import create_multipage_pdf


class StepPdfPreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.store = Store(self.folder / "workshop.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("TEST", "CAR", "SYNTHETIC", "2026")
        self.other_vehicle = self.store.add_vehicle("OTHER", "CAR")
        source = self.folder / "owned.pdf"
        create_multipage_pdf(source, 3)
        self.attachment = import_local_file(
            self.store, self.vehicle, source, "Manual de atelier",
            "Synthetic PDF", "User-owned fixture",
            rights_basis="document_propriu")
        self.article = self.store.db.execute(
            "SELECT article_id FROM attachments WHERE id=?",
            (self.attachment,)).fetchone()[0]
        self.procedure = create_procedure(
            self.store, self.vehicle, "SYNTHETIC", "Test procedure",
            source="User-authored fixture")
        self.step = add_step(
            self.store, self.procedure, "Fictional instruction",
            safety_note="Fictional warning", article_id=self.article)
        self.other_article = self.store.add_article(
            self.vehicle, "Note atelier", "Unrelated", "", "User-owned fixture")

    def preview(self, **kwargs):
        params = dict(step_id=self.step, vehicle_id=self.vehicle,
                      procedure_id=self.procedure, attachment_id=self.attachment)
        params.update(kwargs)
        return read_step_pdf_page(self.store, **params)

    def test_three_pages_are_distinct_and_read_only(self):
        before = self.store.db.total_changes
        pixels = []
        for number in (1, 2, 3):
            image, count = self.preview(page_number=number)
            self.assertEqual(count, 3)
            self.assertEqual(image.mode, "RGB")
            pixels.append(image.getpixel((10, 10)))
        self.assertEqual(len(set(pixels)), 3)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")
        with self.assertRaisesRegex(ValueError, "Pagina PDF nu există"):
            self.preview(page_number=4)

    def test_scope_and_ids_reject_sqlite_coercion(self):
        before = self.store.db.total_changes
        with self.assertRaises(ValueError):
            self.preview(vehicle_id=self.other_vehicle)
        for invalid in (True, 1.0, "1", None, 0, -1):
            for key in ("step_id", "vehicle_id", "procedure_id",
                        "attachment_id", "page_number"):
                with self.subTest(field=key, invalid=repr(invalid)):
                    with self.assertRaises(ValueError):
                        self.preview(**{key: invalid})
        self.assertEqual(self.store.db.total_changes, before)

    def test_revoked_rights_block_pdf(self):
        set_metadata(self.store, self.attachment, "Manual de atelier",
                     "Synthetic PDF", "User-owned fixture",
                     rights_basis="neconfirmat")
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "Drepturi neconfirmate"):
            self.preview()
        self.assertEqual(self.store.db.total_changes, before)

    def test_relinked_step_and_reassigned_attachment_are_rejected(self):
        update_step(self.store, self.step, "Fictional instruction",
                    "Fictional warning", self.other_article)
        with self.assertRaisesRegex(ValueError, "nu mai aparține"):
            self.preview()
        update_step(self.store, self.step, "Fictional instruction",
                    "Fictional warning", self.article)
        self.store.db.execute(
            "UPDATE attachments SET article_id=? WHERE id=?",
            (self.other_article, self.attachment))
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError, "nu mai aparține"):
            self.preview()

    def test_step_relinked_during_render_is_rejected(self):
        from step_pdf_preview import read_verified_pdf_page as original

        def relink(*args, **kwargs):
            result = original(*args, **kwargs)
            update_step(self.store, self.step, "Fictional instruction",
                        "Fictional warning", self.other_article)
            return result

        with patch("step_pdf_preview.read_verified_pdf_page", side_effect=relink):
            with self.assertRaisesRegex(ValueError, "modificat"):
                self.preview()

    def test_attachment_reassigned_during_render_is_rejected(self):
        from step_pdf_preview import read_verified_pdf_page as original

        def reassign(*args, **kwargs):
            result = original(*args, **kwargs)
            self.store.db.execute(
                "UPDATE attachments SET article_id=? WHERE id=?",
                (self.other_article, self.attachment))
            self.store.db.commit()
            return result

        with patch("step_pdf_preview.read_verified_pdf_page", side_effect=reassign):
            with self.assertRaisesRegex(ValueError, "reasociat"):
                self.preview()

    def test_rights_revoked_during_render_are_rechecked(self):
        from step_pdf_preview import read_verified_pdf_page as original

        def revoke(*args, **kwargs):
            result = original(*args, **kwargs)
            set_metadata(self.store, self.attachment, "Manual de atelier",
                         "Synthetic PDF", "User-owned fixture",
                         rights_basis="neconfirmat")
            return result

        with patch("step_pdf_preview.read_verified_pdf_page", side_effect=revoke):
            with self.assertRaisesRegex(ValueError, "Drepturi neconfirmate"):
                self.preview()

    def test_gui_navigates_pages_and_clears_revoked_preview(self):
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
        preview = popup.preview_pdf_attachment(self.attachment)
        self.assertIsNotNone(preview)
        self.addCleanup(preview.destroy)
        self.assertEqual(preview.pdf_page_count, 3)
        self.assertEqual(preview.pdf_page_number.get(), 1)
        self.assertIsNotNone(preview.pdf_photo)
        self.assertTrue(preview.pdf_next())
        self.assertEqual(preview.pdf_page_number.get(), 2)
        self.assertTrue(preview.pdf_next())
        self.assertEqual(preview.pdf_page_number.get(), 3)
        self.assertFalse(preview.pdf_next())
        self.assertTrue(preview.pdf_previous())
        self.assertEqual(preview.pdf_page_number.get(), 2)
        self.assertEqual(self.store.db.total_changes, before)
        set_metadata(self.store, self.attachment, "Manual de atelier",
                     "Synthetic PDF", "User-owned fixture",
                     rights_basis="neconfirmat")
        before = self.store.db.total_changes
        with patch("tkinter.messagebox.showerror") as error:
            self.assertFalse(preview.pdf_next())
            self.assertTrue(error.called)
            self.assertTrue(preview.pdf_invalidated)
            self.assertIsNone(preview.pdf_photo)
            self.assertEqual(preview.pdf_page_label.get(), "Previzualizare invalidată")
            self.assertFalse(preview.pdf_previous())
            self.assertIsNone(popup.preview_pdf_attachment(self.attachment))
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
