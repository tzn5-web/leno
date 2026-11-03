"""Regression coverage for live search-hit ownership and Unicode casefolding.

Only synthetic, locally authored data is used.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import add_step, create_procedure
from procedure_search_hits import list_procedure_hits
from procedure_search_live import validate_live_hit


class LiveSearchDocumentRegression(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / "search-document.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "A")
        self.other_vehicle = self.store.add_vehicle("SYNTHETIC", "B")
        self.article = self.store.add_article(
            self.vehicle, "Notes", "Schematic KEYWORD", "Original synthetic text", "OWNED")
        self.procedure = create_procedure(
            self.store, self.vehicle, "TEST", "Synthetic procedure", source="OWNED")
        self.step = add_step(
            self.store, self.procedure, "Check reference", article_id=self.article)

    def document_hit(self):
        return next(
            hit for hit in list_procedure_hits(self.store, self.vehicle, "KEYWORD")
            if hit["field"] == "Titlu document"
        )

    def test_document_title_change_invalidates_cached_hit_without_writes(self):
        hit = self.document_hit()
        before = self.store.db.total_changes
        self.assertTrue(validate_live_hit(self.store, self.vehicle, hit, "keyword"))
        self.assertEqual(self.store.db.total_changes, before)
        self.store.db.execute(
            "UPDATE articles SET title=? WHERE id=?", ("Updated title", self.article))
        self.store.db.commit()
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "changed"):
            validate_live_hit(self.store, self.vehicle, hit, "KEYWORD")
        self.assertEqual(self.store.db.total_changes, before)

    def test_document_vehicle_reassignment_invalidates_cached_hit(self):
        hit = self.document_hit()
        self.store.db.execute(
            "UPDATE articles SET vehicle_id=? WHERE id=?",
            (self.other_vehicle, self.article))
        self.store.db.commit()
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle, hit, "KEYWORD")

    def test_rejects_boolean_and_noninteger_hit_identifiers(self):
        hit = self.document_hit()
        for field, value in (
            ("procedure_id", True), ("step_id", 1.0),
            ("article_id", str(self.article)), ("article_id", False)
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_live_hit(self.store, self.vehicle, {**hit, field: value}, "KEYWORD")


if __name__ == "__main__":
    unittest.main()
