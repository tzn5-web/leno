"""Regression: paginated procedure search preserves scope and stable navigation.

All records are synthetic. Search and live validation must remain read-only.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step
from procedure_search_hits import list_procedure_hits, filter_hit_indices, next_hit_index
from procedure_search_live import validate_live_hit


class ProcedureSearchPaginationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Store(Path(tmp.name) / "pagination.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "A")
        self.other = self.store.add_vehicle("SYNTHETIC", "B")
        for vehicle in (self.vehicle, self.other):
            pid = create_procedure(
                self.store, vehicle, "TEST", "SYNTH-NEEDLE procedure",
                summary="SYNTH-NEEDLE summary", source="LOCAL")
            add_step(self.store, pid, "SYNTH-NEEDLE instruction",
                     safety_note="SYNTH-NEEDLE warning")

    def test_pages_match_unsliced_results_and_do_not_cross_vehicle(self):
        before = self.store.db.total_changes
        full = list_procedure_hits(self.store, self.vehicle, "SYNTH-NEEDLE")
        self.assertEqual(len(full), 4)
        pages = [
            list_procedure_hits(self.store, self.vehicle, "SYNTH-NEEDLE",
                                limit=2, offset=offset)
            for offset in (0, 2, 4)
        ]
        self.assertEqual(pages[0] + pages[1], full)
        self.assertEqual(pages[2], [])
        self.assertTrue(all(validate_live_hit(
            self.store, self.vehicle, hit, "SYNTH-NEEDLE") for hit in full))
        self.assertEqual(self.store.db.total_changes, before)

    def test_field_filter_and_navigation_do_not_mutate_hits(self):
        hits = list_procedure_hits(self.store, self.vehicle, "SYNTH-NEEDLE")
        original = [dict(hit) for hit in hits]
        warning = filter_hit_indices(hits, "Avertisment pas")
        self.assertEqual(len(warning), 1)
        self.assertEqual(hits[warning[0]]["field"], "Avertisment pas")
        self.assertEqual(next_hit_index(len(warning), None, -1), 0)
        self.assertEqual(next_hit_index(len(warning), 0, 1), 0)
        self.assertEqual(hits, original)

    def test_foreign_vehicle_hit_cannot_be_reused(self):
        foreign = list_procedure_hits(self.store, self.other, "SYNTH-NEEDLE")
        self.assertTrue(foreign)
        for hit in foreign:
            with self.subTest(field=hit["field"]), self.assertRaises(ValueError):
                validate_live_hit(self.store, self.vehicle, hit, "SYNTH-NEEDLE")


if __name__ == "__main__":
    unittest.main()
