"""Regression: document provenance search is scoped to the owning vehicle.

Only synthetic user-owned fixtures are used; no repair specifications.
"""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import (
    add_step, create_procedure, ensure_schema, list_procedures,
    list_reference_articles, list_steps, procedure_text,
)


class ProcedureProvenanceScopeTests(unittest.TestCase):
    def test_foreign_document_provenance_never_leaks_into_search_or_export(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "provenance.sqlite3")
            try:
                ensure_schema(store)
                own = store.add_vehicle("SYNTH", "OWN", "TEST")
                foreign = store.add_vehicle("SYNTH", "OTHER", "TEST")
                pid = create_procedure(
                    store, own, "Example", "Local procedure",
                    source="OWN_PROCEDURE_SOURCE")
                article = store.add_article(
                    own, "Diagram", "PRIVATE_DOCUMENT_TITLE",
                    "PRIVATE_DOCUMENT_BODY", "PRIVATE_DOCUMENT_SOURCE")
                add_step(store, pid, "SAFE_LOCAL_INSTRUCTION", article_id=article)
                self.assertEqual(
                    [r["id"] for r in list_procedures(
                        store, own, "PRIVATE_DOCUMENT_SOURCE")], [pid])
                store.db.execute(
                    "UPDATE articles SET vehicle_id=? WHERE id=?",
                    (foreign, article))
                store.db.commit()
                changes = store.db.total_changes
                for secret in (
                    "PRIVATE_DOCUMENT_TITLE",
                    "PRIVATE_DOCUMENT_BODY",
                    "PRIVATE_DOCUMENT_SOURCE",
                ):
                    with self.subTest(secret=secret):
                        self.assertEqual(list_procedures(store, own, secret), [])
                        self.assertEqual(list_reference_articles(store, pid, secret), [])
                        self.assertNotIn(secret, procedure_text(store, pid))
                text = procedure_text(store, pid)
                self.assertIn("SAFE_LOCAL_INSTRUCTION", text)
                self.assertIn("AVERTISMENT REFERINȚĂ", text)
                self.assertIsNone(list_steps(store, pid)[0]["reference_source"])
                self.assertEqual(store.db.total_changes, changes)
                self.assertEqual(
                    store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
