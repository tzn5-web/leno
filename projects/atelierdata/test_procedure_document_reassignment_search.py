"""Regression: moving a document to another vehicle revokes search visibility.

Synthetic fixtures only; no technical specifications or proprietary content.
"""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import (
    add_step, create_procedure, ensure_schema, list_procedures,
    list_reference_articles, list_steps,
)


class ProcedureDocumentReassignmentSearchTests(unittest.TestCase):
    def test_reassigned_document_is_not_searchable_but_step_remains(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "reassignment.sqlite3")
            try:
                ensure_schema(store)
                original = store.add_vehicle("SYNTH", "A", "TEST")
                other = store.add_vehicle("SYNTH", "B", "TEST")
                procedure = create_procedure(
                    store, original, "Synthetic system", "Synthetic procedure",
                    source="USER-OWNED TEST")
                article = store.add_article(
                    original, "Diagram", "REASSIGNED_PRIVATE_TITLE",
                    "REASSIGNED_PRIVATE_BODY", "USER-OWNED TEST")
                add_step(store, procedure, "VISIBLE_STEP_MARKER", article_id=article)
                self.assertEqual(
                    [row["id"] for row in list_procedures(
                        store, original, "REASSIGNED_PRIVATE_TITLE")],
                    [procedure])
                store.db.execute(
                    "UPDATE articles SET vehicle_id=? WHERE id=?", (other, article))
                store.db.commit()
                before = store.db.total_changes
                for token in ("REASSIGNED_PRIVATE_TITLE", "REASSIGNED_PRIVATE_BODY"):
                    with self.subTest(token=token):
                        self.assertEqual(list_procedures(store, original, token), [])
                        self.assertEqual(
                            list_reference_articles(store, procedure, token), [])
                self.assertEqual(
                    [row["id"] for row in list_procedures(
                        store, original, "VISIBLE_STEP_MARKER")], [procedure])
                steps = list_steps(store, procedure)
                self.assertEqual(len(steps), 1)
                self.assertIsNone(steps[0]["reference_title"])
                self.assertIsNone(steps[0]["reference_source"])
                self.assertEqual(store.db.total_changes, before)
                self.assertEqual(store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
