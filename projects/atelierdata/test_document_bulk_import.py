"""Synthetic bulk import of private PDFs, PNG and TXT, with SHA dedup and scope."""
import tempfile,unittest
from pathlib import Path
from atelierdata import Store
from document_bulk_import import bulk_import_folder
from document_library import list_library

class BulkImportTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.db=Store(self.root/"db.sqlite3");self.addCleanup(self.db.close)
        self.vehicle=self.db.add_vehicle("Nissan","Micra","CR12DE","2006","Benzină")
        self.files=self.root/"files";self.files.mkdir()
        (self.files/"guide.pdf").write_bytes(b"%PDF-1.4\nSynthetic test only")
        (self.files/"schematic.png").write_bytes(b"\x89PNG\r\n\x1a\nSynthetic test only")
        (self.files/"readme.exe").write_bytes(b"MZ NOT EXECUTED")
        (self.files/"sub").mkdir()
        (self.files/"sub"/"test.txt").write_text("synthetic",encoding="utf8")

    def run_import(self,**kwargs):
        data=dict(store=self.db,vehicle_id=self.vehicle,folder=self.files,
                  source_name="Sursă locală de test",rights_basis="document_propriu")
        data.update(kwargs)
        return bulk_import_folder(**data)

    def test_import_supported_files_only(self):
        result=self.run_import()
        self.assertEqual(result["imported"],3,result)
        self.assertEqual(result["duplicates"],0,result)
        self.assertEqual(len(list_library(self.db,make="Nissan")),3)
        self.assertEqual(self.db.db.execute("SELECT COUNT(*) FROM attachments").fetchone()[0],3)

    def test_dedup_exact_vehicle(self):
        self.run_import()
        second=self.run_import()
        self.assertEqual(second["duplicates"],3,second)
        self.assertEqual(second["imported"],0,second)

    def test_rights_required_and_no_writes(self):
        with self.assertRaises(ValueError):self.run_import(rights_basis="neconfirmat")
        self.assertEqual(self.db.stats()[1],0)

    def test_invalid_vehicle_rejected(self):
        with self.assertRaises(ValueError):self.run_import(vehicle_id=999)

    def test_scope_only_first_level(self):
        result=self.run_import(include_subfolders=False)
        self.assertEqual(result["imported"],2)

    def test_empty_files_report_failure_not_full_abort(self):
        (self.files/"empty.pdf").write_bytes(b"")
        report=self.run_import()
        self.assertEqual(report["imported"],3)
        self.assertEqual(len(report["failed"]),1)

if __name__=="__main__":unittest.main()
