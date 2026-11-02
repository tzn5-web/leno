"""Synthetic PDF preview tests: authorization, scope, integrity and page bounds."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from atelierdata import Store
from document_library import import_local_file, set_metadata
from document_pdf_preview import read_verified_pdf_page
from test_workshop_atlas_viewer import create_minimal_pdf


def create_multipage_pdf(path, page_count=3):
    """Create a small, fully synthetic PDF with visually distinct pages."""
    if not 1 <= page_count <= 10:
        raise ValueError("Synthetic page count out of range")
    refs=b" ".join(f"{3+2*i} 0 R".encode("ascii") for i in range(page_count))
    objects=[
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["+refs+b"] /Count "+str(page_count).encode()+b" >>",
    ]
    colors=((1,0,0),(0,1,0),(0,0,1))
    for i in range(page_count):
        red,green,blue=colors[i%len(colors)]
        content=f"{red} {green} {blue} rg\n0 0 200 200 re f\n".encode("ascii")
        objects.extend((
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            b"/Resources << >> /Contents "+str(4+2*i).encode()+b" 0 R >>",
            b"<< /Length "+str(len(content)).encode()+b" >>\nstream\n"
            +content+b"endstream",
        ))
    data=bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets=[0]
    for index,element in enumerate(objects,1):
        offsets.append(len(data))
        data+=str(index).encode()+b" 0 obj\n"+element+b"\nendobj\n"
    xref=len(data)
    data+=f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        data+=f"{offset:010d} 00000 n \n".encode()
    data+=b"trailer\n<< /Root 1 0 R /Size "+str(len(objects)+1).encode()+b" >>\nstartxref\n"
    data+=str(xref).encode()+b"\n%%EOF\n"
    path.write_bytes(data)


class PdfPreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = Store(self.root / "test.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("Synthetic", "Vehicle", "TEST", "2008")
        self.other = self.store.add_vehicle("Other", "Vehicle")
        source = self.root / "owned.pdf"
        create_minimal_pdf(source)
        self.attachment = import_local_file(
            self.store, self.vehicle, source, "Manual de atelier",
            "Owned synthetic PDF", "Local synthetic fixture",
            rights_basis="document_propriu")
        self.article = self.store.db.execute(
            "SELECT article_id FROM attachments WHERE id=?",
            (self.attachment,)).fetchone()[0]

    def preview(self, **kwargs):
        return read_verified_pdf_page(
            self.store, self.attachment, self.vehicle, self.article, **kwargs)

    def test_render_page_is_offline_read_only_and_scoped(self):
        before = self.store.db.total_changes
        image, count = self.preview(page_number=1)
        self.assertEqual(count, 1)
        self.assertEqual(image.mode, "RGB")
        self.assertGreaterEqual(image.width, 200)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")
        with self.assertRaisesRegex(ValueError, "vehiculului"):
            read_verified_pdf_page(self.store, self.attachment, self.other, self.article)
        with self.assertRaisesRegex(ValueError, "articolului"):
            read_verified_pdf_page(self.store, self.attachment, self.vehicle, self.article + 99)
        self.assertEqual(self.store.db.total_changes, before)

    def test_page_number_and_size_limits(self):
        for number in (0, -1, True, 1.5, "1"):
            with self.subTest(number=number), self.assertRaisesRegex(ValueError, "Pagina PDF"):
                self.preview(page_number=number)
        with self.assertRaisesRegex(ValueError, "Pagina PDF nu există"):
            self.preview(page_number=2)
        with patch("document_pdf_preview.MAX_PDF_PREVIEW_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "32 MiB"):
                self.preview()
        with patch("document_pdf_preview.MAX_PDF_PREVIEW_PAGES", 0):
            with self.assertRaisesRegex(ValueError, "Număr de pagini"):
                self.preview()

    def test_revoked_rights_and_invalid_pdf_are_blocked(self):
        set_metadata(self.store, self.attachment, "Manual de atelier",
                     "Owned synthetic PDF", "Local synthetic fixture",
                     rights_basis="neconfirmat")
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "Drepturi neconfirmate"):
            self.preview()
        self.assertEqual(self.store.db.total_changes, before)
        bad = self.root / "invalid.pdf"
        bad.write_bytes(b"%PDF-1.4\\nnot a PDF")
        invalid = import_local_file(
            self.store, self.vehicle, bad, "Manual de atelier",
            "Invalid synthetic PDF", "Local synthetic fixture",
            rights_basis="document_propriu")
        with self.assertRaisesRegex(ValueError, "PDF invalid|Număr de pagini"):
            read_verified_pdf_page(self.store, invalid, self.vehicle)

    def test_three_distinct_pages_and_out_of_range_are_read_only(self):
        source=self.root / "three-pages.pdf"
        create_multipage_pdf(source,3)
        attachment=import_local_file(
            self.store,self.vehicle,source,"Manual de atelier",
            "Owned synthetic multipage PDF","Local synthetic fixture",
            rights_basis="document_propriu")
        before=self.store.db.total_changes
        pixels=[]
        for number in (1,2,3):
            image,count=read_verified_pdf_page(
                self.store,attachment,vehicle_id=self.vehicle,page_number=number)
            self.assertEqual(count,3)
            self.assertEqual(image.mode,"RGB")
            pixels.append(image.getpixel((10,10)))
        self.assertEqual(len(set(pixels)),3)
        with self.assertRaisesRegex(ValueError,"Pagina PDF nu există"):
            read_verified_pdf_page(
                self.store,attachment,vehicle_id=self.vehicle,page_number=4)
        self.assertEqual(self.store.db.total_changes,before)

    def test_rehashes_bytes_after_preflight(self):
        from document_pdf_preview import verified_library_file as original

        def change_after_preflight(*args, **kwargs):
            path = original(*args, **kwargs)
            path.write_bytes(path.read_bytes() + b"changed")
            return path

        before = self.store.db.total_changes
        with patch("document_pdf_preview.verified_library_file",
                   side_effect=change_after_preflight):
            with self.assertRaisesRegex(ValueError, "modificat sau corupt"):
                self.preview()
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
