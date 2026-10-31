"""Synthetic step-level search tests; no real repair instructions or OEM data."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step
from procedure_search_hits import filter_hit_indices, list_procedure_hits, next_hit_index


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

    def test_field_filter_stable_indices_and_no_mutation(self):
        hits = self.hits("OWN")
        original = [dict(hit) for hit in hits]
        all_indices = filter_hit_indices(hits)
        self.assertEqual(all_indices, list(range(len(hits))))
        doc_indices = filter_hit_indices(hits, "Conținut document")
        self.assertEqual([hits[i]["field"] for i in doc_indices],
                         ["Conținut document"])
        self.assertEqual(filter_hit_indices(hits, "Inexistent"), [])
        self.assertEqual(hits, original)
        self.assertTrue(all(isinstance(i, int) for i in all_indices))

    def test_field_filter_navigation_skips_hidden_rows(self):
        self.db.db.execute(
            "UPDATE procedures SET title=?,source=? WHERE id=?",
            ("FILTER-KEY title", "FILTER-KEY source", self.pid))
        self.db.db.execute(
            "UPDATE procedure_steps SET instruction=?,safety_note=? WHERE id=?",
            ("FILTER-KEY instruction", "FILTER-KEY warning", self.sid))
        self.db.db.commit()
        before = self.db.db.total_changes
        hits = self.hits("FILTER-KEY")
        indices = filter_hit_indices(hits, "Instrucțiune pas")
        self.assertEqual(len(indices), 1)
        self.assertEqual(hits[indices[0]]["step_id"], self.sid)
        self.assertEqual(hits[indices[0]]["field"], "Instrucțiune pas")
        self.assertEqual(indices[next_hit_index(len(indices), 0, 1)], indices[0])
        self.assertEqual(self.db.db.total_changes, before)

    def test_result_navigation_wrap_and_empty(self):
        self.assertIsNone(next_hit_index(0))
        self.assertEqual(next_hit_index(3), 0)
        self.assertEqual(next_hit_index(3, direction=-1), 2)
        self.assertEqual(next_hit_index(3, 0, -1), 2)
        self.assertEqual(next_hit_index(3, 2, 1), 0)
        self.assertEqual(next_hit_index(3, 1, 1), 2)
        self.assertEqual(next_hit_index(1, 0, 1), 0)

    def test_result_navigation_rejects_invalid_indices(self):
        for count in (-1, 1001, True, 2.5, "2"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                next_hit_index(count)
        for direction in (0, 2, True, "1"):
            with self.subTest(direction=direction), self.assertRaises(ValueError):
                next_hit_index(2, direction=direction)
        for selected in (-1, 2, True, 1.2, "1", 0):
            count = 0 if selected == 0 and type(selected) is int else 2
            with self.subTest(selected=selected, count=count), self.assertRaises(ValueError):
                next_hit_index(count, selected)

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

    def test_multiple_fields_per_step_are_visible_with_provenance(self):
        # A single step may match an instruction, warning, diagram and source.
        # Every match must remain navigable, in deterministic field order.
        self.db.db.execute(
            "UPDATE procedures SET system=?,title=? WHERE id=?",
            ("MATCH-KEY system", "MATCH-KEY procedure", self.pid))
        self.db.db.execute(
            "UPDATE procedure_steps SET instruction=?,safety_note=? WHERE id=?",
            ("MATCH-KEY instruction", "MATCH-KEY warning", self.sid))
        self.db.db.execute(
            "UPDATE articles SET title=?,category=?,content=?,source=? WHERE id=?",
            ("MATCH-KEY title", "MATCH-KEY category",
             "MATCH-KEY content", "MATCH-KEY provenance", self.doc))
        self.db.db.commit()
        before = self.db.db.total_changes
        hits = self.hits("MATCH-KEY")
        self.assertEqual([h["field"] for h in hits], [
            "Titlu procedură", "Sistem", "Instrucțiune pas",
            "Avertisment pas", "Titlu document", "Categorie document",
            "Conținut document", "Proveniență document"])
        self.assertEqual([h["step_id"] for h in hits[:2]], [None, None])
        self.assertTrue(all(h["step_id"] == self.sid for h in hits[2:]))
        self.assertEqual([h["source"] for h in hits[2:4]],
                         ["OWN-PROVENANCE"] * 2)
        self.assertEqual([h["source"] for h in hits[4:]],
                         ["MATCH-KEY provenance"] * 4)
        self.assertEqual(len(self.hits("MATCH-KEY", limit=3)), 3)
        self.assertEqual(self.db.db.total_changes, before)

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
