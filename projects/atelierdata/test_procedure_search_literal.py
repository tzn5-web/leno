"""Literal procedure search and vehicle-isolation regression tests.

All records are synthetic; no licensed repair instructions are bundled.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import add_step, create_procedure, list_procedures


class ProcedureLiteralSearchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / "search.sqlite3")
        self.addCleanup(self.store.close)
        self.car = self.store.add_vehicle("TEST", "CAR A")
        self.other = self.store.add_vehicle("TEST", "CAR B")
        self.pid = create_procedure(
            self.store, self.car, "Sistem demonstrativ",
            "Procedură sintetică", source="SURSA-PROPRIE-TEST"
        )
        self.foreign_pid = create_procedure(
            self.store, self.other, "Alt sistem",
            "Altă procedură", source="FOREIGN-PROVENANCE"
        )
        self.article = self.store.add_article(
            self.car, "Note atelier", r"Diagram\%_ 100",
            "CONTINUT-DOCUMENT-TEST", "LICENTA-TEST"
        )
        self.foreign_article = self.store.add_article(
            self.other, "Note atelier", "FOREIGN-SECRET-DO-NOT-LEAK",
            "FOREIGN-CONTENT-DO-NOT-LEAK", "FOREIGN-DOCUMENT-SOURCE"
        )
        self.step = add_step(
            self.store, self.pid, "PAS 100%_ TEST",
            safety_note="ATENTIE-SINTETICA", article_id=self.article
        )

    def ids(self, search, vehicle=None):
        return [r["id"] for r in list_procedures(self.store, vehicle, search)]

    def test_percent_underscore_and_backslash_are_literal(self):
        self.assertEqual(self.ids("%_", self.car), [self.pid])
        self.assertEqual(self.ids("100%_", self.car), [self.pid])
        self.assertEqual(self.ids(r"\%_", self.car), [self.pid])
        self.assertEqual(self.ids("100%", self.car), [self.pid])
        self.assertEqual(self.ids("_", self.other), [])
        self.assertEqual(self.ids("%", self.other), [])
        self.assertEqual(self.ids("\\", self.other), [])

    def test_search_metadata_step_warning_and_document_fields(self):
        for term in ("Sistem demonstrativ", "Procedură sintetică",
                     "SURSA-PROPRIE-TEST", "PAS 100%_ TEST",
                     "ATENTIE-SINTETICA", "Diagram", "Note atelier",
                     "LICENTA-TEST", "CONTINUT-DOCUMENT-TEST"):
            with self.subTest(term=term):
                self.assertEqual(self.ids(term, self.car), [self.pid])
        self.assertEqual(self.ids("NO-SUCH-DATA", self.car), [])

    def test_cross_vehicle_document_reference_is_never_searchable(self):
        # Simulate a corrupted DB, bypassing normal same-vehicle validation.
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.foreign_article, self.step)
        )
        self.store.db.commit()
        for term in ("FOREIGN-SECRET-DO-NOT-LEAK",
                     "FOREIGN-CONTENT-DO-NOT-LEAK",
                     "FOREIGN-DOCUMENT-SOURCE"):
            with self.subTest(term=term):
                self.assertEqual(self.ids(term, self.car), [])
        self.assertEqual(self.ids("ATENTIE-SINTETICA", self.car), [self.pid])

    def test_global_search_is_scoped_to_each_procedure(self):
        self.assertEqual(self.ids("FOREIGN-PROVENANCE"), [self.foreign_pid])
        self.assertEqual(self.ids("FOREIGN-PROVENANCE", self.car), [])
        self.assertEqual(self.ids("SURSA-PROPRIE-TEST"), [self.pid])
        self.assertEqual(self.ids("SURSA-PROPRIE-TEST", self.other), [])

    def test_invalid_search_and_read_only_guarantee(self):
        for bad in (None, 1, True, "\0", "a"*201):
            with self.subTest(value=repr(bad)):
                with self.assertRaises(ValueError):
                    list_procedures(self.store, self.car, bad)
        for bad in (True, 0, -1, "1"):
            with self.subTest(vehicle=repr(bad)):
                with self.assertRaises(ValueError):
                    list_procedures(self.store, bad, "test")
        before = self.store.db.total_changes
        self.assertEqual(self.ids("PAS", self.car), [self.pid])
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
