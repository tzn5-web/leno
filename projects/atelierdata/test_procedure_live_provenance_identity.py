"""Regression coverage for live search-hit provenance and document identity.

Only synthetic, user-owned SQLite records are used.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import add_step, create_procedure
from procedure_search_hits import list_procedure_hits
from procedure_search_live import validate_live_hit


class LiveProvenanceRegression(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / "provenance.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "OWNED")
        self.other_vehicle = self.store.add_vehicle("SYNTHETIC", "OTHER")
        self.doc = self.store.add_article(
            self.vehicle, "Notes", "SAME-TITLE", "Owned synthetic document", "SOURCE-ALPHA")
        self.replacement = self.store.add_article(
            self.vehicle, "Notes", "SAME-TITLE", "Replacement document", "SOURCE-BETA")
        self.pid = create_procedure(
            self.store, self.vehicle, "TEST", "Synthetic repair", source="OWNED")
        self.sid = add_step(self.store, self.pid, "Synthetic step", article_id=self.doc)

    def find(self, term, label):
        return next(hit for hit in list_procedure_hits(self.store, self.vehicle, term)
                    if hit["field"] == label)

    def test_same_title_relinked_document_is_stale(self):
        hit = self.find("SAME-TITLE", "Titlu document")
        before = self.store.db.total_changes
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.replacement, self.sid))
        self.store.db.commit()
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle, hit, "SAME-TITLE")
        self.assertEqual(self.store.db.total_changes, before + 1)

    def test_provenance_change_invalidates_original_hit(self):
        hit = self.find("SOURCE-ALPHA", "Proveniență document")
        self.store.db.execute(
            "UPDATE articles SET source=? WHERE id=?", ("SOURCE-REPLACED", self.doc))
        self.store.db.commit()
        before = self.store.db.total_changes
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle, hit, "SOURCE-ALPHA")
        self.assertEqual(self.store.db.total_changes, before)

    def test_cross_vehicle_document_move_invalidates_hit(self):
        hit = self.find("SAME-TITLE", "Titlu document")
        self.store.db.execute(
            "UPDATE articles SET vehicle_id=? WHERE id=?",
            (self.other_vehicle, self.doc))
        self.store.db.commit()
        before = self.store.db.total_changes
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle, hit, "SAME-TITLE")
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
