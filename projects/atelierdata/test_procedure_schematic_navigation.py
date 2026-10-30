"""Synthetic integration tests for procedure-to-schematic navigation (no OEM data)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image
from atelierdata import Store
from atelierdata_extensions import attach_document, resolve_document
from repair_procedures import (add_step, create_procedure, list_steps,
                               update_step)
from schematic_viewer import (get_schematic_reference, image_metadata,
                              list_schematic_articles)


class ProcedureSchematicNavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "test.sqlite3")
        self.addCleanup(self.store.close)
        self.car = self.store.add_vehicle("TEST", "VEHICLE")
        self.other_car = self.store.add_vehicle("OTHER", "VEHICLE")
        self.schematic = self.store.add_article(
            self.car, "Scheme electrice", "Synthetic diagram",
            "Fictional test illustration", "SYNTHETIC SOURCE")
        self.other_schematic = self.store.add_article(
            self.other_car, "Scheme electrice", "Other vehicle diagram",
            "", "SYNTHETIC SOURCE")
        self.note = self.store.add_article(
            self.car, "Note atelier", "Ordinary article", "", "SYNTHETIC SOURCE")
        self.procedure = create_procedure(
            self.store, self.car, "TEST SYSTEM", "Synthetic procedure",
            source="SYNTHETIC SOURCE")

    def test_same_vehicle_schematic_and_provenance(self):
        row = get_schematic_reference(self.store, self.car, self.schematic)
        self.assertEqual(row["id"], self.schematic)
        self.assertEqual(row["source"], "SYNTHETIC SOURCE")
        self.assertEqual(row["category"], "Scheme electrice")
        self.assertEqual(len(list_schematic_articles(self.store, self.car)), 1)

    def test_reject_cross_vehicle_non_schematic_missing_and_invalid_id(self):
        for ref in (self.other_schematic, self.note, 987654, True,
                    "1 OR 1=1", None, -1):
            with self.subTest(reference=ref):
                with self.assertRaises(ValueError):
                    get_schematic_reference(self.store, self.car, ref)

    def test_step_link_to_verified_image_and_deletion(self):
        image_path = self.root / "synthetic.png"
        Image.new("RGB", (32, 16), (40, 60, 80)).save(image_path)
        attachment_id = attach_document(self.store, self.schematic, image_path)
        sid = add_step(self.store, self.procedure, "Fictional step",
                       safety_note="Test warning", article_id=self.schematic)
        row = list_steps(self.store, self.procedure)[0]
        self.assertEqual(row["id"], sid)
        self.assertEqual(row["article_id"], self.schematic)
        get_schematic_reference(self.store, self.car, row["article_id"])
        verified = resolve_document(self.store, attachment_id)
        self.assertEqual(image_metadata(verified)["width"], 32)
        update_step(self.store, sid, "Fictional step", "Test warning", self.note)
        with self.assertRaises(ValueError):
            get_schematic_reference(self.store, self.car,
                                    list_steps(self.store, self.procedure)[0]["article_id"])
        update_step(self.store, sid, "Fictional step", "Test warning", self.schematic)
        self.store.delete_article(self.schematic)
        row = list_steps(self.store, self.procedure)[0]
        self.assertIsNone(row["article_id"])
        self.assertEqual(row["safety_note"], "Test warning")


if __name__ == "__main__":
    unittest.main()
