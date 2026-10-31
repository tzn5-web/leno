"""Unit tests for local authorized-document library. Synthetic local files only."""
import json
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from atelierdata_extensions import attach_document,resolve_document
from atelierdata_backup import backup_bundle,restore_bundle
from document_library import (
    DOCUMENT_TYPES,ACCESS_RIGHTS,ensure_schema,set_metadata,import_local_file,
    list_library,verified_library_file,document_attachment)

class DocumentLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=Store(self.root/"database.sqlite3")
        self.addCleanup(self.db.close)
        self.mitsubishi=self.db.add_vehicle("Mitsubishi","Lancer","4A91","2008","Benzină")
        self.skoda=self.db.add_vehicle("Skoda","Octavia","BKC","2005-2009","Diesel")
        self.pdf=self.root/"sample.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")

    def import_sample(self,vehicle=None,**overrides):
        params=dict(vehicle_id=vehicle if vehicle is not None else self.mitsubishi,
           source_path=self.pdf,category="Manual de atelier",title="Test 4A91",
           source_name="Manual privat de test",rights_basis="document_propriu",
           language="ro",market="EU",revision="2026",
           applicability_note="Verificat doar pentru exemplul sintetic")
        params.update(overrides)
        return import_local_file(self.db,**params)

    def test_schema_migration_and_existing_attachment(self):
        article=self.db.add_article(self.mitsubishi,"Scheme electrice","Schema veche","", "arhivă")
        attachment=attach_document(self.db,article,self.pdf)
        self.assertEqual(len(list_library(self.db,make="Mitsubishi")),1)
        original=list_library(self.db)[0]
        self.assertIsNone(original["document_type"])
        self.assertEqual(original["article_title"],"Schema veche")
        set_metadata(self.db,attachment,"Schemă electrică","Schema verificată","Autor cunoscut")
        updated=list_library(self.db)[0]
        self.assertEqual(updated["display_title"],"Schema verificată")
        self.assertEqual(updated["rights_basis"],"neconfirmat")

    def test_import_exact_vehicle_and_source_provenance(self):
        attachment=self.import_sample(source_url="https://example.org/authorized")
        row=list_library(self.db,make="Mitsubishi",model="Lancer",engine="4A91",year="2008")[0]
        self.assertEqual(row["vehicle_id"],self.mitsubishi)
        self.assertEqual(row["attachment_id"],attachment)
        self.assertEqual(row["rights_basis"],"document_propriu")
        self.assertEqual(row["market"],"EU")
        self.assertEqual(row["source_url"],"https://example.org/authorized")
        self.assertEqual(verified_library_file(self.db,attachment,self.mitsubishi).read_bytes(),self.pdf.read_bytes())

    def test_filter_second_make_and_engine(self):
        self.import_sample()
        self.import_sample(vehicle=self.skoda,title="Test BKC")
        self.assertEqual(len(list_library(self.db,make="Skoda")),1)
        self.assertEqual(len(list_library(self.db,engine="4A91")),1)
        self.assertEqual(len(list_library(self.db,year="2007")),1)
        self.assertEqual(len(list_library(self.db,year="2013")),0)
        self.assertEqual(len(list_library(self.db,category="Manual de atelier")),2)

    def test_invalid_year_and_literal_search(self):
        self.import_sample(title="Test 100%_literal")
        self.assertEqual(len(list_library(self.db,query="100%_literal")),1)
        self.assertEqual(len(list_library(self.db,query="100%_missing")),0)
        with self.assertRaisesRegex(ValueError,"YYYY"):
            list_library(self.db,year="2008 OR 1=1")

    def test_import_refuses_unconfirmed_rights_without_creating_article(self):
        with self.assertRaisesRegex(ValueError,"fără confirmarea"):
            self.import_sample(rights_basis="neconfirmat")
        self.assertEqual(self.db.stats()[1],0)
        self.assertEqual(len(list_library(self.db)),0)

    def test_import_rejects_unknown_vehicle_and_bad_category(self):
        with self.assertRaises(ValueError):
            self.import_sample(vehicle=999)
        with self.assertRaises(ValueError):
            self.import_sample(category="Kernel drivers")
        self.assertEqual(len(list_library(self.db)),0)

    def test_reject_http_and_local_source_urls(self):
        for url in ("http://example.org","file:///C:/license.txt","https://localhost/private",
                    "https://user:pass@example.org","https://127.0.0.1/"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    self.import_sample(source_url=url)
        self.assertEqual(self.db.stats()[1],0)

    def test_file_integrity_and_vehicle_scope_enforced(self):
        attachment=self.import_sample()
        with self.assertRaisesRegex(ValueError,"nu aparține"):
            verified_library_file(self.db,attachment,self.skoda)
        path=verified_library_file(self.db,attachment)
        path.write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError,"corupt"):
            verified_library_file(self.db,attachment)
        with self.assertRaises(ValueError):
            set_metadata(self.db,attachment,"Manual de atelier","Title","Source")

    def test_duplicate_metadata_edit_is_upsert_not_duplicate(self):
        a=self.import_sample()
        set_metadata(self.db,a,"Schemă electrică","Electrică","Autor","",
                     rights_basis="permisiune_scrisa")
        set_metadata(self.db,a,"Schemă electrică","Electrică revizuită","Autor","",
                     rights_basis="permisiune_scrisa")
        self.assertEqual(len(list_library(self.db)),1)
        self.assertEqual(list_library(self.db)[0]["display_title"],"Electrică revizuită")
        self.assertEqual(len(list_library(self.db,only_indexed=True)),1)

    def test_complete_backup_restores_metadata_and_bytes(self):
        a=self.import_sample()
        archive=self.root/"bundle.zip"
        backup_bundle(self.db,archive)
        dest=restore_bundle(archive,self.root/"restored")
        restored=Store(dest)
        try:
            rows=list_library(restored,engine="4A91")
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["source_name"],"Manual privat de test")
            self.assertEqual(verified_library_file(restored,rows[0]["attachment_id"]).read_bytes(),
                             self.pdf.read_bytes())
        finally:restored.close()

    def test_metadata_removed_when_article_deleted(self):
        a=self.import_sample()
        row=document_attachment(self.db,a)
        self.db.delete_article(row["article_id"])
        self.assertEqual(self.db.db.execute("SELECT COUNT(*) FROM library_documents").fetchone()[0],0)

if __name__=="__main__":
    unittest.main()
