"""Synthetic PDF text layer indexing; no OCR, no vendor manuals."""
import tempfile,unittest
from pathlib import Path
from atelierdata import Store
from atelierdata_extensions import attach_document
from atelierdata_backup import backup_bundle,restore_bundle
from pdf_text_index import index_pdf,search_pdf_text

def pdf_text(path,text):
    # A valid minimal text-layer PDF with an embedded standard font declaration.
    text=text.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
    stream=f"BT /F1 15 Tf 20 140 Td ({text}) Tj ET\n".encode("ascii")
    items=[
       b"<< /Type /Catalog /Pages 2 0 R >>",
       b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
       b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
       b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"endstream",
       b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    raw=bytearray(b"%PDF-1.4\n"); offsets=[0]
    for i,body in enumerate(items,1):
        offsets.append(len(raw))
        raw+=str(i).encode()+b" 0 obj\n"+body+b"\nendobj\n"
    start=len(raw);raw+=b"xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets[1:]:raw+=f"{offset:010d} 00000 n \n".encode()
    raw+=b"trailer\n<< /Root 1 0 R /Size 6 >>\nstartxref\n"+str(start).encode()+b"\n%%EOF\n"
    path.write_bytes(raw)

class PdfSearchTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.db=Store(self.root/"db.sqlite3");self.addCleanup(self.db.close)
        self.m=self.db.add_vehicle("Mitsubishi","Lancer","4A91","2008","Benzina")
        self.b=self.db.add_vehicle("BMW","320d","M47","2007","Diesel")
        src=self.root/"synthetic.pdf"
        pdf_text(src,"SYNTHETIC COMPONENT LOCATION ONLY")
        aid=self.db.add_article(self.m,"Proceduri de reparație","Synthetic test","","TEST")
        self.doc=attach_document(self.db,aid,src)

    def test_index_and_literal_search_vehicle_scoped(self):
        stats=index_pdf(self.db,self.m,self.doc)
        self.assertEqual(stats["pages_total"],1)
        self.assertEqual(stats["pages_with_text"],1,stats)
        rows=search_pdf_text(self.db,self.m,"COMPONENT")
        self.assertEqual(len(rows),1,rows)
        self.assertEqual(rows[0]["page_number"],1)
        self.assertIn("LOCATION",rows[0]["excerpt"])
        self.assertEqual(search_pdf_text(self.db,self.b,"COMPONENT"),[])
        self.assertEqual(search_pdf_text(self.db,self.m,"MISSING"),[])

    def test_no_cross_vehicle_index(self):
        with self.assertRaises(ValueError):
            index_pdf(self.db,self.b,self.doc)

    def test_duplicate_index_replaces_old(self):
        index_pdf(self.db,self.m,self.doc)
        index_pdf(self.db,self.m,self.doc)
        self.assertEqual(len(search_pdf_text(self.db,self.m,"SYNTHETIC")),1)

    def test_backup_preserves_local_pdf_index(self):
        index_pdf(self.db,self.m,self.doc)
        archive=self.root/"bundle.zip";backup_bundle(self.db,archive)
        restored=Store(restore_bundle(archive,self.root/"other"))
        try:self.assertEqual(len(search_pdf_text(restored,self.m,"COMPONENT")),1)
        finally:restored.close()

    def test_search_validation(self):
        for value in (""," "*5,"Q"*121):
            with self.assertRaises(ValueError):search_pdf_text(self.db,self.m,value)
        with self.assertRaises(ValueError):search_pdf_text(self.db,self.m,"text",limit=10000)

if __name__=="__main__":unittest.main()
