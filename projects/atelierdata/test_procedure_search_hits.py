"""Synthetic step-level search tests; no real repair instructions or OEM data."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step
from procedure_search_hits import list_procedure_hits


class ProcedureSearchHitTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Store(Path(temp.name) / "search-hits.sqlite3")
        self.addCleanup(self.db.close)
        self.car = self.db.add_vehicle("TEST", "CAR ONE")
        self.other = self.db.add_vehicle("TEST", "CAR TWO")
        self.pid = create_procedure(
            self.db, self.car, "Synthetic system", "Synthetic procedure",
            precautions="GENERAL-ALERT", source="OWN-PROVENANCE")
        self.doc = self.db.add_article(
            self.car, "Scheme electrice", "DIAGRAM-REF-77",
            "OWN-DOC-CONTENT", "DOC-PROVENANCE")
        self.foreign_doc = self.db.add_article(
            self.other, "Scheme electrice", "SECRET-FOREIGN-REF",
            "SECRET-FOREIGN-CONTENT", "SECRET-FOREIGN-SOURCE")
        self.sid = add_step(
            self.db, self.pid, "SIMULATED-STEP 100%_",
            safety_note="SYNTHETIC-WARNING", article_id=self.doc)
        self.other_pid = create_procedure(
            self.db, self.other, "Other system", "Foreign procedure",
            source="FOREIGN-PROVENANCE")
        self.other_sid = add_step(self.db, self.other_pid, "FOREIGN-STEP")

    def hits(self, query, vehicle=None, limit=250):
        return list_procedure_hits(
            self.db, self.car if vehicle is None else vehicle, query, limit=limit)

    def test_literal_percent_underscore_and_backslash(self):
        for term in ("100%_", "%_", "100%"):
            with self.subTest(term=term):
                hits = self.hits(term)
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]["step_id"], self.sid)
                self.assertEqual(hits[0]["field"], "Instrucțiune pas")
        self.assertEqual(self.hits("100%X"), [])
        self.assertEqual(self.hits("SIMULATED\\STEP"), [])

    def test_step_warning_and_document_provenance(self):
        for term, expected_field, expected_source in (
            ("SYNTHETIC-WARNING", "Avertisment pas", "OWN-PROVENANCE"),
            ("DIAGRAM-REF-77", "Titlu document", "DOC-PROVENANCE"),
            ("OWN-DOC-CONTENT", "Conținut document", "DOC-PROVENANCE"),
            ("DOC-PROVENANCE", "Proveniență document", "DOC-PROVENANCE"),
        ):
            with self.subTest(term=term):
                hits = self.hits(term)
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]["field"], expected_field)
                self.assertEqual(hits[0]["source"], expected_source)
                self.assertEqual(hits[0]["step_id"], self.sid)
                self.assertEqual(hits[0]["step_number"], 1)

    def test_metadata_hit_without_step(self):
        hits = self.hits("GENERAL-ALERT")
        self.assertEqual(len(hits), 1)
        self.assertIsNone(hits[0]["step_id"])
        self.assertEqual(hits[0]["field"], "Avertisment general")
        self.assertEqual(hits[0]["source"], "OWN-PROVENANCE")

    def test_cross_vehicle_corruption_never_exposes_document(self):
        self.db.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.foreign_doc, self.sid))
        self.db.db.commit()
        for term in ("SECRET-FOREIGN-REF", "SECRET-FOREIGN-CONTENT",
                     "SECRET-FOREIGN-SOURCE"):
            with self.subTest(term=term):
                self.assertEqual(self.hits(term), [])
        self.assertEqual(self.hits("SYNTHETIC-WARNING")[0]["step_id"], self.sid)
        self.assertEqual(self.hits("FOREIGN-STEP"), [])
        other = self.hits("FOREIGN-STEP", self.other)
        self.assertEqual(other[0]["step_id"], self.other_sid)

    def test_limit_and_deterministic_order(self):
        second = add_step(self.db, self.pid, "SIMULATED-STEP 100%_ SECOND")
        hits = self.hits("SIMULATED-STEP", limit=1)
        self.assertEqual([h["step_id"] for h in hits], [self.sid])
        hits = self.hits("SIMULATED-STEP")
        self.assertEqual([h["step_id"] for h in hits], [self.sid, second])

    def test_reject_invalid_search_vehicle_and_limit(self):
        for bad in ("", "  ", "\0", "x"*201, None, 7):
            with self.subTest(query=repr(bad)):
                with self.assertRaises(ValueError):
                    self.hits(bad)
        for bad in (True, 0, -1, 1.5, 1001):
            with self.subTest(limit=repr(bad)):
                with self.assertRaises(ValueError):
                    self.hits("SIMULATED", limit=bad)
        for bad in (True, 0, "1"):
            with self.subTest(vehicle=repr(bad)):
                with self.assertRaises(ValueError):
                    self.hits("SIMULATED", vehicle=bad)

    def test_read_only_and_missing_document(self):
        before = self.db.db.total_changes
        self.assertEqual(self.hits("OWN-DOC-CONTENT")[0]["step_id"], self.sid)
        self.assertEqual(self.db.db.total_changes, before)
        self.db.db.execute("DELETE FROM articles WHERE id=?", (self.doc,))
        self.db.db.commit()
        self.assertEqual(self.hits("OWN-DOC-CONTENT"), [])
        self.assertEqual(self.db.db.execute("PRAGMA quick_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
