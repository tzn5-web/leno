"""Integration regression: literal Unicode search across owned step/document fields.

Uses only synthetic local records. The search and live navigation check must
agree on casefold semantics without treating SQL wildcards as patterns.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import add_step, create_procedure
from procedure_search_hits import list_procedure_hits
from procedure_search_live import validate_live_hit


class LiteralSearchIntegration(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "literal-search.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "LOCAL")
        self.other = self.store.add_vehicle("SYNTHETIC", "FOREIGN")
        self.doc = self.store.add_article(
            self.vehicle, "Owned", "Straße %_ diagram",
            "Synthetic document body", "LOCAL-OWNED")
        self.foreign = self.store.add_article(
            self.other, "Private", "Straße %_ confidential",
            "Synthetic private text", "OTHER")
        self.pid = create_procedure(
            self.store, self.vehicle, "TEST", "Owned procedure", source="LOCAL")
        self.sid = add_step(self.store, self.pid, "Check Straße %_ wiring",
                            safety_note="Use synthetic warning", article_id=self.doc)

    def test_unicode_casefold_and_literal_wildcards_agree_with_live_check(self):
        before = self.store.db.total_changes
        for term in ("STRASSE", "%_", "strasse %_"):
            with self.subTest(term=term):
                hits = list_procedure_hits(self.store, self.vehicle, term)
                self.assertTrue(hits)
                self.assertTrue(any(hit["field"] == "Titlu document" for hit in hits))
                for hit in hits:
                    self.assertTrue(validate_live_hit(self.store, self.vehicle, hit, term))
        self.assertEqual(self.store.db.total_changes, before)

    def test_foreign_document_is_not_searchable_through_corrupt_reference(self):
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.foreign, self.sid))
        self.store.db.commit()
        before = self.store.db.total_changes
        hits = list_procedure_hits(self.store, self.vehicle, "confidential")
        self.assertEqual(hits, [])
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
