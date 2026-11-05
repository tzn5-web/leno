"""Regression: procedure search is literal, scoped and read-only.

All strings and vehicle records below are synthetic fixtures.
"""
import unittest

from atelierdata import Store
from repair_procedures import (
    ensure_schema, create_procedure, add_step, list_procedures,
    list_reference_articles,
)


class ProcedureLiteralSearchTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "literal-search.sqlite3")
        self.addCleanup(self.store.close)
        ensure_schema(self.store)
        self.vehicle = self.store.add_vehicle("SYNTH", "A", "TEST")
        self.other_vehicle = self.store.add_vehicle("SYNTH", "B", "TEST")
        self.procedure = create_procedure(
            self.store, self.vehicle, "Mock subsystem", "Neutral procedure",
            source="USER-OWNED-SYNTHETIC")
        self.document = self.store.add_article(
            self.vehicle, "Mock diagrams", "Café_100% drawing",
            "Placeholder only", "USER-OWNED-SYNTHETIC")
        add_step(self.store, self.procedure, "Neutral instruction",
                 article_id=self.document)
        self.foreign_document = self.store.add_article(
            self.other_vehicle, "Mock diagrams", "FOREIGN_SECRET_TOKEN",
            "FOREIGN_BODY_TOKEN", "OTHER-VEHICLE")

    def test_literal_wildcards_and_unicode_casefold(self):
        before = self.store.db.total_changes
        for term in ("café_100%", "CAFÉ_100%", "100%", "_100%"):
            with self.subTest(term=term):
                self.assertEqual(
                    [row["id"] for row in list_procedures(
                        self.store, self.vehicle, term)],
                    [self.procedure])
                self.assertEqual(
                    [row["id"] for row in list_reference_articles(
                        self.store, self.procedure, term)],
                    [self.document])
        for term in ("caféX100%", "100X", "FOREIGN_SECRET_TOKEN",
                     "FOREIGN_BODY_TOKEN"):
            with self.subTest(term=term):
                self.assertEqual(
                    list_procedures(self.store, self.vehicle, term), [])
                self.assertEqual(
                    list_reference_articles(self.store, self.procedure, term), [])
        self.assertEqual(self.store.db.total_changes, before)

    def test_foreign_document_cannot_be_found_via_corrupt_link(self):
        step = self.store.db.execute(
            "SELECT id FROM procedure_steps WHERE procedure_id=?",
            (self.procedure,)).fetchone()[0]
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.foreign_document, step))
        self.store.db.commit()
        before = self.store.db.total_changes
        for term in ("FOREIGN_SECRET_TOKEN", "FOREIGN_BODY_TOKEN"):
            self.assertEqual(
                list_procedures(self.store, self.vehicle, term), [])
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
