"""Regression checks for live search-hit identity and literal Unicode matching.

All fixtures are synthetic. No proprietary technical data is used.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import add_step, create_procedure
from procedure_search_hits import list_procedure_hits
from procedure_search_live import validate_live_hit


class SearchHitIdentityBoundaryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "identity.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "A")
        self.other_vehicle = self.store.add_vehicle("SYNTHETIC", "B")
        self.document = self.store.add_article(
            self.vehicle, "Same title", "REFERENCE-KEY", "Body", "LICENSED-TEST")
        self.other_document = self.store.add_article(
            self.vehicle, "Same title", "REFERENCE-KEY", "Body", "LICENSED-TEST")
        self.pid = create_procedure(
            self.store, self.vehicle, "TEST", "Procedure", source="LICENSED-TEST")
        self.sid = add_step(self.store, self.pid, "Instruction", article_id=self.document)

    def test_document_identity_cannot_be_swapped_even_when_text_matches(self):
        hit = next(h for h in list_procedure_hits(self.store, self.vehicle, "REFERENCE-KEY")
                   if h["field"] == "Titlu document")
        before = self.store.db.total_changes
        self.assertTrue(validate_live_hit(self.store, self.vehicle, hit, "REFERENCE-KEY"))
        with self.assertRaises(ValueError):
            validate_live_hit(self.store, self.vehicle,
                              {**hit, "article_id": self.other_document}, "REFERENCE-KEY")
        self.assertEqual(self.store.db.total_changes, before)

    def test_reject_boolean_float_and_string_identity_spoofing(self):
        hit = next(h for h in list_procedure_hits(self.store, self.vehicle, "REFERENCE-KEY")
                   if h["field"] == "Titlu document")
        before = self.store.db.total_changes
        for key in ("procedure_id", "step_id", "article_id"):
            for bad in (True, 1.0, str(hit[key]), 0, None):
                with self.subTest(key=key, value=repr(bad)):
                    with self.assertRaises(ValueError):
                        validate_live_hit(self.store, self.vehicle,
                                          {**hit, key: bad}, "REFERENCE-KEY")
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
