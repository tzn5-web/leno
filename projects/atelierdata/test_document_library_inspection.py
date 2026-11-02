"""Read-only document preflight tests; synthetic user-owned fixtures only."""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from document_library import (import_local_file, inspect_library_entry, set_metadata,
                              verified_library_file, read_verified_text_preview)
from atelierdata_extensions import resolve_document


class LibraryInspectionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = Store(self.root / "data.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle(
            "Synthetic", "Vehicle", "TEST", "2008", "Benzina")
        self.source = self.root / "fixture.pdf"
        self.source.write_bytes(b"%PDF-1.4\n%%EOF\n")
        self.attachment = import_local_file(
            self.store, self.vehicle, self.source, "Manual de atelier",
            "Synthetic fixture", "User fixture", rights_basis="document_propriu")
        self.article = self.store.db.execute(
            "SELECT article_id FROM attachments WHERE id=?",
            (self.attachment,)).fetchone()[0]

    def check(self):
        return inspect_library_entry(
            self.store, self.attachment, self.vehicle, self.article)

    def test_valid_preflight_is_read_only_and_does_not_launch(self):
        before = self.store.db.total_changes
        result = self.check()
        self.assertTrue(result["ok"], result)
        self.assertIn("SHA256", result["message"])
        self.assertIn("declarate", result["message"])
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_corrupted_and_missing_files_fail_without_sqlite_writes(self):
        path = resolve_document(self.store, self.attachment)
        path.write_bytes(b"changed")
        before = self.store.db.total_changes
        result = self.check()
        self.assertFalse(result["ok"])
        self.assertIn("corupt", result["message"])
        self.assertEqual(self.store.db.total_changes, before)
        path.unlink()
        result = self.check()
        self.assertFalse(result["ok"])
        self.assertIn("lipsă", result["message"])
        self.assertEqual(self.store.db.total_changes, before)

    def test_masquerading_pdf_and_images_are_inventory_only(self):
        """Correct SHA256 does not make mislabeled binary data safe to launch."""
        for suffix in (".pdf", ".png", ".jpg", ".jpeg"):
            with self.subTest(suffix=suffix):
                source = self.root / ("masquerade" + suffix)
                source.write_bytes(b"MZ\x90\x00synthetic non-document")
                attachment = import_local_file(
                    self.store, self.vehicle, source, "Manual de atelier",
                    "Synthetic masquerade", "User fixture",
                    rights_basis="document_propriu")
                article = self.store.db.execute(
                    "SELECT article_id FROM attachments WHERE id=?",
                    (attachment,)).fetchone()[0]
                before = self.store.db.total_changes
                # Existing internal byte integrity/indexing remains unchanged.
                self.assertEqual(resolve_document(self.store, attachment).read_bytes(),
                                 source.read_bytes())
                result = inspect_library_entry(
                    self.store, attachment, self.vehicle, article)
                self.assertFalse(result["ok"], result)
                self.assertIn("Semnătură fișier invalidă", result["message"])
                with self.assertRaisesRegex(ValueError, "Semnătură fișier invalidă"):
                    verified_library_file(
                        self.store, attachment, vehicle_id=self.vehicle,
                        article_id=article, require_declared_rights=True)
                self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_binary_and_empty_txt_are_inventory_only(self):
        """Single-file TXT imports must pass the same launch gate as batch imports."""
        fixtures = (
            ("exe", b"MZ" + bytes([0x90, 0]) + b"synthetic"),
            ("archive", b"PK" + bytes([3, 4]) + b"synthetic"),
            ("nul", b"synthetic" + bytes([0]) + b"payload"),
            ("empty", b""),
        )
        for label, payload in fixtures:
            with self.subTest(label=label):
                source = self.root / ("disguised_" + label + ".txt")
                source.write_bytes(payload)
                attachment = import_local_file(
                    self.store, self.vehicle, source, "Manual de atelier",
                    "Synthetic " + label, "User fixture",
                    rights_basis="document_propriu")
                article = self.store.db.execute(
                    "SELECT article_id FROM attachments WHERE id=?",
                    (attachment,)).fetchone()[0]
                before = self.store.db.total_changes
                # The SHA256 still matches; the extra gate is for GUI launch only.
                self.assertEqual(resolve_document(self.store, attachment).read_bytes(), payload)
                result = inspect_library_entry(
                    self.store, attachment, self.vehicle, article)
                self.assertFalse(result["ok"], result)
                self.assertIn("TXT nu pare text", result["message"])
                with self.assertRaisesRegex(ValueError, "TXT nu pare text"):
                    verified_library_file(
                        self.store, attachment, vehicle_id=self.vehicle,
                        article_id=article, require_declared_rights=True)
                self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_plain_utf8_txt_remains_openable(self):
        source = self.root / "valid.txt"
        source.write_text("Procedură sintetică autorizată\n", encoding="utf-8")
        attachment = import_local_file(
            self.store, self.vehicle, source, "Manual de atelier",
            "Synthetic text", "User fixture", rights_basis="document_propriu")
        before = self.store.db.total_changes
        result = inspect_library_entry(self.store, attachment, self.vehicle)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.store.db.total_changes, before)

    def test_internal_txt_preview_is_utf8_read_only_and_vehicle_scoped(self):
        source = self.root / "preview.txt"
        source.write_text("Pași de test — conținut sintetic\\n", encoding="utf-8-sig")
        attachment = import_local_file(
            self.store, self.vehicle, source, "Manual de atelier",
            "Synthetic preview", "User fixture", rights_basis="document_propriu")
        article = self.store.db.execute(
            "SELECT article_id FROM attachments WHERE id=?", (attachment,)).fetchone()[0]
        before = self.store.db.total_changes
        self.assertEqual(
            read_verified_text_preview(self.store, attachment, self.vehicle, article),
            "Pași de test — conținut sintetic\\n")
        self.assertEqual(self.store.db.total_changes, before)
        with self.assertRaisesRegex(ValueError, "vehiculului"):
            read_verified_text_preview(self.store, attachment, self.vehicle + 999, article)
        with self.assertRaisesRegex(ValueError, "articolului"):
            read_verified_text_preview(self.store, attachment, self.vehicle, article + 999)
        self.assertEqual(self.store.db.total_changes, before)

    def test_internal_txt_preview_rejects_oversized_invalid_and_late_binary(self):
        for label, payload, error in (
            ("oversized", b"A" * (1024 * 1024 + 1), "prea mare"),
            ("invalid_utf8", b"invalid " + bytes([255]), "UTF-8"),
            ("late_nul", b"A" * 5000 + bytes([0]), "control"),
        ):
            with self.subTest(label=label):
                source = self.root / (label + ".txt")
                source.write_bytes(payload)
                attachment = import_local_file(
                    self.store, self.vehicle, source, "Manual de atelier",
                    "Synthetic " + label, "User fixture",
                    rights_basis="document_propriu")
                before = self.store.db.total_changes
                with self.assertRaisesRegex(ValueError, error):
                    read_verified_text_preview(self.store, attachment, self.vehicle)
                self.assertEqual(self.store.db.total_changes, before)

    def test_internal_txt_preview_requires_current_rights_and_txt_extension(self):
        with self.assertRaisesRegex(ValueError, "numai fișiere TXT"):
            read_verified_text_preview(self.store, self.attachment, self.vehicle, self.article)
        source = self.root / "revoked.txt"
        source.write_text("Synthetic test only", encoding="utf-8")
        attachment = import_local_file(
            self.store, self.vehicle, source, "Manual de atelier",
            "Synthetic revoked", "User fixture", rights_basis="document_propriu")
        set_metadata(self.store, attachment, "Manual de atelier",
                     "Synthetic revoked", "User fixture", rights_basis="neconfirmat")
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "Drepturi neconfirmate"):
            read_verified_text_preview(self.store, attachment, self.vehicle)
        self.assertEqual(self.store.db.total_changes, before)

    def test_rights_revoked_after_selection_fail_closed(self):
        set_metadata(self.store, self.attachment, "Manual de atelier",
                     "Synthetic fixture", "User fixture",
                     rights_basis="neconfirmat")
        before = self.store.db.total_changes
        result = self.check()
        self.assertFalse(result["ok"])
        self.assertIn("Drepturi neconfirmate", result["message"])
        self.assertEqual(self.store.db.total_changes, before)

    def test_reassigned_article_and_vehicle_are_rejected(self):
        new_article = self.store.add_article(
            self.vehicle, "Manual de atelier", "Other article", "", "User")
        self.store.db.execute("UPDATE attachments SET article_id=? WHERE id=?",
                              (new_article, self.attachment))
        self.store.db.commit()
        before = self.store.db.total_changes
        self.assertIn("articolului", self.check()["message"])
        self.assertEqual(self.store.db.total_changes, before)
        foreign = self.store.add_vehicle("Foreign", "Vehicle")
        foreign_article = self.store.add_article(
            foreign, "Manual de atelier", "Foreign article", "", "User")
        self.store.db.execute("UPDATE attachments SET article_id=? WHERE id=?",
                              (foreign_article, self.attachment))
        self.store.db.commit()
        before = self.store.db.total_changes
        self.assertIn("vehiculului", self.check()["message"])
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
