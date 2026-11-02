"""Synthetic PDF preview tests: authorization, scope, integrity and page bounds."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from atelierdata import Store
from document_library import import_local_file, set_metadata
from document_pdf_preview import read_verified_pdf_page
from test_workshop_atlas_viewer import create_minimal_pdf


class PdfPreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = Store(self.root / "test.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("Synthetic", "Vehicle", "TEST", "2008")
        self.other = self.store.add_vehicle("Other", "Vehicle")
        source = self.root / "owned.pdf"
        create_minimal_pdf(source)
        self.attachment = import_local_file(
            self.store, self.vehicle, source, "Manual de atelier",
            "Owned synthetic PDF", "Local synthetic fixture",
            rights_basis="document_propriu")
        self.article = self.store.db.execute(
            "SELECT article_id FROM attachments WHERE id=?",
            (self.attachment,)).fetchone()[0]

    def preview(self, **kwargs):
        return read_verified_pdf_page(
            self.store, self.attachment, self.vehicle, self.article, **kwargs)

    def test_render_page_is_offline_read_only_and_scoped(self):
        before = self.store.db.total_changes
        image, count = self.preview(page_number=1)
        self.assertEqual(count, 1)
        self.assertEqual(image.mode, "RGB")
        self.assertGreaterEqual(image.width, 200)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")
        with self.assertRaisesRegex(ValueError, "vehiculului"):
            read_verified_pdf_page(self.store, self.attachment, self.other, self.article)
        with self.assertRaisesRegex(ValueError, "articolului"):
            read_verified_pdf_page(self.store, self.attachment, self.vehicle, self.article + 99)
        self.assertEqual(self.store.db.total_changes, before)

    def test_page_number_and_size_limits(self):
        for number in (0, -1, True, 1.5, "1"):
            with self.subTest(number=number), self.assertRaisesRegex(ValueError, "Pagina PDF"):
                self.preview(page_number=number)
        with self.assertRaisesRegex(ValueError, "Pagina PDF nu există"):
            self.preview(page_number=2)
        with patch("document_pdf_preview.MAX_PDF_PREVIEW_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "32 MiB"):
                self.preview()
        with patch("document_pdf_preview.MAX_PDF_PREVIEW_PAGES", 0):
            with self.assertRaisesRegex(ValueError, "Număr de pagini"):
                self.preview()

    def test_revoked_rights_and_invalid_pdf_are_blocked(self):
        set_metadata(self.store, self.attachment, "Manual de atelier",
                     "Owned synthetic PDF", "Local synthetic fixture",
                     rights_basis="neconfirmat")
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "Drepturi neconfirmate"):
            self.preview()
        self.assertEqual(self.store.db.total_changes, before)
        bad = self.root / "invalid.pdf"
        bad.write_bytes(b"%PDF-1.4\\nnot a PDF")
        invalid = import_local_file(
            self.store, self.vehicle, bad, "Manual de atelier",
            "Invalid synthetic PDF", "Local synthetic fixture",
            rights_basis="document_propriu")
        with self.assertRaisesRegex(ValueError, "PDF invalid|Număr de pagini"):
            read_verified_pdf_page(self.store, invalid, self.vehicle)

    def test_rehashes_bytes_after_preflight(self):
        from document_pdf_preview import verified_library_file as original

        def change_after_preflight(*args, **kwargs):
            path = original(*args, **kwargs)
            path.write_bytes(path.read_bytes() + b"changed")
            return path

        before = self.store.db.total_changes
        with patch("document_pdf_preview.verified_library_file",
                   side_effect=change_after_preflight):
            with self.assertRaisesRegex(ValueError, "modificat sau corupt"):
                self.preview()
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
