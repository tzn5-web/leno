"""GUI hit metadata must not render untrusted Unicode controls from SQLite."""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step
from procedure_search_hits import list_procedure_hits


class SearchHitMetadataDisplayTests(unittest.TestCase):
    def test_titles_and_sources_are_safe_without_mutating_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "test.sqlite3")
            try:
                vehicle = store.add_vehicle("TEST", "DISPLAY")
                title = "Own\u202e procedure"
                source = "OWN\nSOURCE\u200b"
                pid = create_procedure(
                    store, vehicle, "Synthetic", title,
                    source=source)
                add_step(store, pid, "MATCH-STEP")
                before = store.db.total_changes
                hits = list_procedure_hits(store, vehicle, "MATCH-STEP")
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]["procedure_title"], "Own  procedure")
                self.assertEqual(hits[0]["source"], "OWN SOURCE ")
                self.assertEqual(store.db.total_changes, before)
                row = store.db.execute(
                    "SELECT title, source FROM procedures WHERE id=?", (pid,)
                ).fetchone()
                self.assertEqual((row["title"], row["source"]), (title, source))
            finally:
                store.close()

    def test_document_provenance_controls_are_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "test.sqlite3")
            try:
                vehicle = store.add_vehicle("TEST", "DISPLAY")
                pid = create_procedure(
                    store, vehicle, "Synthetic", "Own procedure", source="OWN")
                document_source = "DOC\u202e\nPROVENANCE"
                article = store.add_article(
                    vehicle, "Synthetic", "MATCH-DOC", "Own content", document_source)
                add_step(store, pid, "Own step", article_id=article)
                before = store.db.total_changes
                hits = list_procedure_hits(
                    store, vehicle, "MATCH-DOC", field="Categorie document")
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]["source"], "DOC  PROVENANCE")
                self.assertEqual(store.db.total_changes, before)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
