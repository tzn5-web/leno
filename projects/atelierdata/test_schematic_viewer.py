"""Synthetic diagram tests: verify bounds, ownership, and verified attachments."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from atelierdata import Store
from atelierdata_extensions import attach_document, resolve_document
from schematic_viewer import (clamp_zoom, fit_zoom, image_metadata,
                              list_schematic_articles, MAX_IMAGE_PIXELS)

class SchematicViewerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.store=Store(self.root/"catalog.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle=self.store.add_vehicle("Synthetic","Test car")
        self.second=self.store.add_vehicle("Other synthetic","Test car")
        self.article=self.store.add_article(self.vehicle,"Scheme electrice",
            "Diagramă inventată", "Conținut demonstrativ, nu instrucțiuni auto", "DEMO")
    def test_scheme_scoping_and_search(self):
        self.store.add_article(self.vehicle,"Siguranțe și relee","Panou fictiv","","Test")
        self.store.add_article(self.vehicle,"Motor","Document obișnuit","","Test")
        self.store.add_article(self.second,"Scheme electrice","Nu aparține vehiculului","","Test")
        found=list_schematic_articles(self.store,self.vehicle)
        self.assertEqual({x["title"] for x in found},
                         {"Diagramă inventată","Panou fictiv"})
        self.assertEqual(len(list_schematic_articles(self.store,self.vehicle,"inventată")),1)
    def test_image_validity_verified_storage(self):
        source=self.root/"drawing.png"
        Image.new("RGB",(640,320),(20,40,80)).save(source)
        metadata=image_metadata(source)
        self.assertEqual((metadata["width"],metadata["height"]),(640,320))
        attachment=attach_document(self.store,self.article,source)
        verified=resolve_document(self.store,attachment)
        self.assertEqual(image_metadata(verified)["width"],640)
        verified.write_bytes(b"corrupt")
        with self.assertRaises(ValueError):resolve_document(self.store,attachment)
    def test_nonimage_and_corrupted_content_rejected(self):
        fake=self.root/"fake.png";fake.write_bytes(b"not a PNG")
        with self.assertRaises(ValueError):image_metadata(fake)
        pdf=self.root/"note.pdf";pdf.write_bytes(b"%PDF-1.4\n")
        with self.assertRaises(ValueError):image_metadata(pdf)
        mislabeled=self.root/"bad.jpg"
        Image.new("RGB",(20,20)).save(mislabeled,format="PNG")
        with self.assertRaises(ValueError):image_metadata(mislabeled)
    def test_bounds_and_zoom(self):
        self.assertAlmostEqual(fit_zoom(2000,1000,1000,500),0.5)
        self.assertEqual(clamp_zoom(0.001),0.15)
        self.assertEqual(clamp_zoom(1000),4.0)
        with self.assertRaises(ValueError):fit_zoom(0,400,1000,500)
        self.assertLess(MAX_IMAGE_PIXELS,100_000_000)

if __name__=="__main__":unittest.main()
