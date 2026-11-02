"""Offline authorized image preview tests using generated, synthetic fixtures."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from atelierdata import Store
from atelierdata_extensions import resolve_document
from document_library import import_local_file, set_metadata
from document_image_preview import read_verified_image_preview


class ImagePreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = Store(self.root / "test.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("Synthetic", "Vehicle", "TEST", "2008")
        self.foreign_vehicle = self.store.add_vehicle("Other", "Vehicle")

    def add_image(self, suffix=".png"):
        source = self.root / ("owned" + suffix)
        Image.new("RGB", (3, 2), (15, 40, 80)).save(source)
        attachment = import_local_file(
            self.store, self.vehicle, source, "Manual de atelier",
            "Synthetic image", "User-owned fixture", rights_basis="document_propriu")
        article = self.store.db.execute(
            "SELECT article_id FROM attachments WHERE id=?", (attachment,)).fetchone()[0]
        return attachment, article

    def test_png_jpeg_preview_is_read_only_and_vehicle_scoped(self):
        for suffix in (".png", ".jpg", ".jpeg"):
            with self.subTest(suffix=suffix):
                attachment, article = self.add_image(suffix)
                before = self.store.db.total_changes
                image = read_verified_image_preview(
                    self.store, attachment, self.vehicle, article)
                self.assertEqual(image.size, (3, 2))
                self.assertEqual(image.mode, "RGB")
                self.assertEqual(self.store.db.total_changes, before)
                with self.assertRaisesRegex(ValueError, "vehiculului"):
                    read_verified_image_preview(
                        self.store, attachment, self.foreign_vehicle, article)
                with self.assertRaisesRegex(ValueError, "articolului"):
                    read_verified_image_preview(
                        self.store, attachment, self.vehicle, article + 999)
                self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_preview_rejects_revoked_rights_and_unsupported_format(self):
        attachment, article = self.add_image()
        set_metadata(self.store, attachment, "Manual de atelier",
                     "Synthetic image", "User-owned fixture", rights_basis="neconfirmat")
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "Drepturi neconfirmate"):
            read_verified_image_preview(self.store, attachment, self.vehicle, article)
        self.assertEqual(self.store.db.total_changes, before)
        source = self.root / "owned.txt"
        source.write_text("synthetic", encoding="utf-8")
        txt = import_local_file(self.store, self.vehicle, source, "Manual de atelier",
                                "Synthetic text", "User-owned fixture",
                                rights_basis="document_propriu")
        with self.assertRaisesRegex(ValueError, "numai PNG"):
            read_verified_image_preview(self.store, txt, self.vehicle)

    def test_preview_rejects_oversized_bytes_and_pixels(self):
        attachment, article = self.add_image()
        before = self.store.db.total_changes
        with patch("document_image_preview.MAX_IMAGE_PREVIEW_BYTES", 12):
            with self.assertRaisesRegex(ValueError, "16 MiB"):
                read_verified_image_preview(self.store, attachment, self.vehicle, article)
        with patch("document_image_preview.MAX_IMAGE_PREVIEW_PIXELS", 4):
            with self.assertRaisesRegex(ValueError, "8 megapixeli"):
                read_verified_image_preview(self.store, attachment, self.vehicle, article)
        self.assertEqual(self.store.db.total_changes, before)

    def test_preview_rejects_corrupt_payload_with_valid_stored_hash(self):
        source = self.root / "bad.png"
        source.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-real-image")
        attachment = import_local_file(
            self.store, self.vehicle, source, "Manual de atelier",
            "Synthetic corrupt PNG", "User-owned fixture", rights_basis="document_propriu")
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "Imagine invalidă"):
            read_verified_image_preview(self.store, attachment, self.vehicle)
        self.assertEqual(self.store.db.total_changes, before)

    def test_preview_rehashes_exact_displayed_bytes_after_preflight(self):
        attachment, article = self.add_image()
        from document_image_preview import verified_library_file as original

        def changed_after_preflight(*args, **kwargs):
            path = original(*args, **kwargs)
            path.write_bytes(path.read_bytes() + b"changed-after-preflight")
            return path

        before = self.store.db.total_changes
        with patch("document_image_preview.verified_library_file",
                   side_effect=changed_after_preflight):
            with self.assertRaisesRegex(ValueError, "modificat sau corupt"):
                read_verified_image_preview(self.store, attachment, self.vehicle, article)
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
