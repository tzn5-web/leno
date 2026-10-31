"""Synthetic PDF/image rendering and actual Tkinter atlas GUI smoke.

No imported manufacturer data. No browser access or executable execution.
"""
from __future__ import annotations
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from PIL import Image
from atelierdata import Store
from atelierdata_extensions import attach_document
from workshop_atlas import record_fact
from workshop_atlas_gui import _render_document,open_workshop_atlas

def create_minimal_pdf(path):
    content=b"q\n0 0 1 rg\n15 15 80 80 re f\nQ\n"
    obj=[
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << >> /Contents 4 0 R >>",
        b"<< /Length "+str(len(content)).encode()+b" >>\nstream\n"+content+b"endstream",
    ]
    data=bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets=[0]
    for i,element in enumerate(obj,1):
        offsets.append(len(data))
        data+=str(i).encode()+b" 0 obj\n"+element+b"\nendobj\n"
    xref=len(data)
    data+=b"xref\n0 5\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        data+=f"{offset:010d} 00000 n \n".encode()
    data+=b"trailer\n<< /Root 1 0 R /Size 5 >>\nstartxref\n"
    data+=str(xref).encode()+b"\n%%EOF\n"
    path.write_bytes(data)

class AtlasViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_pdfium_renders_owned_pdf(self):
        pdf=self.root/"onepage.pdf"
        create_minimal_pdf(pdf)
        image,pages=_render_document(pdf)
        self.assertEqual(pages,1)
        self.assertTrue(image.width>=200 and image.height>=200)
        self.assertEqual(image.mode,"RGB")
        with self.assertRaisesRegex(ValueError,"Pagina"):
            _render_document(pdf,page_number=2)

    def test_pillow_image_render_and_page_guard(self):
        path=self.root/"schematic.png"
        Image.new("RGB",(200,120),(255,255,255)).save(path)
        img,pages=_render_document(path)
        self.assertEqual((img.width,img.height,pages),(200,120,1))

    def test_ui_shows_selected_vehicle_and_its_document(self):
        try:root=tk.Tk()
        except tk.TclError as e:
            self.skipTest("GUI display unavailable: "+str(e))
        root.withdraw()
        store=Store(self.root/"data.sqlite3")
        try:
            vid=store.add_vehicle("Mitsubishi","Lancer","4A91","2008","Benzină")
            aid=store.add_article(vid,"Scheme electrice","Synthetic drawing","","TEST")
            path=self.root/"drawing.png"
            Image.new("RGB",(160,100),(255,255,255)).save(path)
            attachment=attach_document(store,aid,path)
            record_fact(store,vid,"Locație componentă","Motor","Sensor sample",
                        "Synthetic test",component_location="Doar fixture")
            class App:pass
            app=App();app.root=root;app.tk=tk;app.db=store;app.vid=vid
            win=open_workshop_atlas(app)
            root.update_idletasks()
            self.assertIsNotNone(win)
            self.assertEqual(len(win.atlas_facts_tree.get_children()),1)
            self.assertIn("Synthetic drawing",win.atlas_document_choice.get())
            self.assertTrue(win.atlas_image_canvas.find_all())
            win.destroy()
        finally:
            store.close()
            root.destroy()

if __name__=="__main__":
    unittest.main()
