"""Synthetic step-linked image preview tests; no proprietary service data."""
from __future__ import annotations

import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from atelierdata import Store
from document_library import import_local_file, set_metadata
from repair_procedures import add_step, create_procedure, update_step
from step_image_preview import read_step_image_preview


class StepImagePreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.store = Store(self.folder / "workshop.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("TEST", "CAR", "SYNTHETIC", "2026")
        self.other_vehicle = self.store.add_vehicle("OTHER", "CAR")
        source = self.folder / "owned.png"
        Image.new("RGB", (4, 3), (40, 70, 100)).save(source)
        self.attachment = import_local_file(
            self.store, self.vehicle, source, "Manual de atelier",
            "Synthetic diagram", "User-owned fixture",
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
        return read_step_image_preview(self.store, **params)

    def test_valid_image_is_read_only_and_scoped(self):
        before = self.store.db.total_changes
        image = self.preview()
        self.assertEqual(image.size, (4, 3))
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")
        with self.assertRaises(ValueError):
            self.preview(vehicle_id=self.other_vehicle)

    def test_revoked_rights_block_image(self):
        set_metadata(self.store, self.attachment, "Manual de atelier",
                     "Synthetic diagram", "User-owned fixture",
                     rights_basis="neconfirmat")
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "Drepturi neconfirmate"):
            self.preview()
        self.assertEqual(self.store.db.total_changes, before)

    def test_relinked_step_or_reassigned_attachment_is_rejected(self):
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

    def test_invalid_ids_never_coerce_sqlite(self):
        before = self.store.db.total_changes
        for invalid in (True, 1.0, "1", None, -1, 0):
            for key in ("step_id", "vehicle_id", "procedure_id", "attachment_id"):
                with self.subTest(invalid=repr(invalid), field=key):
                    with self.assertRaises(ValueError):
                        self.preview(**{key: invalid})
        self.assertEqual(self.store.db.total_changes, before)

    def test_link_changed_while_decoding_rejects_image(self):
        from step_image_preview import read_verified_image_preview as original

        def relink(*args, **kwargs):
            result = original(*args, **kwargs)
            update_step(self.store, self.step, "Fictional instruction",
                        "Fictional warning", self.other_article)
            return result

        with patch("step_image_preview.read_verified_image_preview", side_effect=relink):
            with self.assertRaisesRegex(ValueError, "modificat"):
                self.preview()

    def test_attachment_reassigned_while_decoding_rejects_image(self):
        from step_image_preview import read_verified_image_preview as original

        def reassign(*args, **kwargs):
            result = original(*args, **kwargs)
            self.store.db.execute(
                "UPDATE attachments SET article_id=? WHERE id=?",
                (self.other_article, self.attachment))
            self.store.db.commit()
            return result

        with patch("step_image_preview.read_verified_image_preview", side_effect=reassign):
            with self.assertRaisesRegex(ValueError, "reasociat"):
                self.preview()

    def test_gui_opens_image_and_blocks_revoked_rights(self):
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
        preview = popup.preview_image_attachment(self.attachment)
        self.assertIsNotNone(preview)
        self.addCleanup(preview.destroy)
        self.assertTrue(preview.winfo_exists())
        self.assertIsNotNone(preview.image_photo)
        self.assertEqual(self.store.db.total_changes, before)
        set_metadata(self.store, self.attachment, "Manual de atelier",
                     "Synthetic diagram", "User-owned fixture",
                     rights_basis="neconfirmat")
        before = self.store.db.total_changes
        with patch("tkinter.messagebox.showerror") as error:
            self.assertIsNone(popup.preview_image_attachment(self.attachment))
            self.assertTrue(error.called)
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
