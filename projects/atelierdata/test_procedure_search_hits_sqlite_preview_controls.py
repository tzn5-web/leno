"""SQLite-to-search-preview regression tests using synthetic, owned records only."""
import tempfile
import unittest
import unicodedata
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step
from procedure_search_hits import list_procedure_hits


class SearchPreviewSqliteSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "preview.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("TEST", "PREVIEW")
        self.other = self.store.add_vehicle("TEST", "OTHER")
        self.procedure = create_procedure(
            self.store, self.vehicle, "Synthetic system", "Preview procedure",
            source="OWN-SOURCE")
        self.step = add_step(self.store, self.procedure, "Placeholder instruction")

    def test_warning_preview_sanitizes_controls_but_preserves_original_sqlite(self):
        original = "Avertizare\u202e: verifică schemă\n înainte de test"
        self.store.db.execute(
            "UPDATE procedure_steps SET safety_note=? WHERE id=?",
            (original, self.step))
        self.store.db.commit()
        before = self.store.db.total_changes
        hits = list_procedure_hits(
            self.store, self.vehicle, "schemă", field="Avertisment pas")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["step_id"], self.step)
        self.assertIn("schemă", hits[0]["excerpt"])
        self.assertFalse(any(unicodedata.category(c) in
                             ("Cc", "Cf", "Cs", "Zl", "Zp")
                             for c in hits[0]["excerpt"]))
        self.assertEqual(
            self.store.db.execute(
                "SELECT safety_note FROM procedure_steps WHERE id=?",
                (self.step,)).fetchone()[0], original)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(list_procedure_hits(self.store, self.other, "schemă"), [])

    def test_document_preview_is_vehicle_scoped_and_read_only(self):
        document = self.store.add_article(
            self.vehicle, "Scheme", "SCHEMA-SYNTHETIC",
            "Document\u2028 synthetic reference", "OWN-DOC")
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (document, self.step))
        self.store.db.commit()
        before = self.store.db.total_changes
        hits = list_procedure_hits(
            self.store, self.vehicle, "synthetic", field="Conținut document")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["article_id"], document)
        self.assertNotIn("\u2028", hits[0]["excerpt"])
        self.assertEqual(self.store.db.total_changes, before)
        self.store.db.execute(
            "UPDATE articles SET vehicle_id=? WHERE id=?",
            (self.other, document))
        self.store.db.commit()
        self.assertEqual(list_procedure_hits(
            self.store, self.vehicle, "synthetic", field="Conținut document"), [])
        self.assertEqual(self.store.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
