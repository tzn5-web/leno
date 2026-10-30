"""Synthetic DTC tests. No real vehicle fault definitions are included."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from dtc_catalog import (add_dtc, delete_dtc, dtc_text, ensure_schema, export_dtc, get_dtc,
                         import_dtc, list_dtc, update_dtc)
from repair_procedures import create_procedure


class DtcTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=Store(self.root/"example.sqlite3")
        self.addCleanup(self.db.close)
        ensure_schema(self.db)
        self.vid=self.db.add_vehicle("DEMO MAKE","Model F","TEST MOTOR","N/A")
        self.other=self.db.add_vehicle("DEMO MAKE","Model G","TEST MOTOR 2","N/A")

    def test_create_search_update_remove(self):
        ident=add_dtc(self.db,self.vid,"p0abc","Sistem demo","Cod sintetic",
                      symptoms="Simptom demonstrativ",checks="Verificare fictivă",
                      source="TEST ONLY")
        self.assertEqual(get_dtc(self.db,ident)["code"],"P0ABC")
        self.assertEqual(len(list_dtc(self.db,self.vid,search="simptom")),1)
        self.assertIn("TEST ONLY",dtc_text(self.db,ident))
        update_dtc(self.db,ident,"u0123","Alt sistem demo","Titlu revizuit",
                   source="TEST 2")
        self.assertEqual(get_dtc(self.db,ident)["code"],"U0123")
        delete_dtc(self.db,ident)
        self.assertEqual(len(list_dtc(self.db,self.vid)),0)

    def test_code_format_source_uniqueness(self):
        for code in ("P0", "A0000", "P-999", "P12345", "U123xZ"):
            with self.assertRaises(ValueError):
                add_dtc(self.db,self.vid,code,"TEST","TEST",source="TEST")
        with self.assertRaises(ValueError):
            add_dtc(self.db,self.vid,"P0001","TEST","TEST")
        add_dtc(self.db,self.vid,"C0001","TEST","TEST",source="A")
        with self.assertRaises(ValueError):
            add_dtc(self.db,self.vid,"C0001","Another system","Other",source="A")
        add_dtc(self.db,self.vid,"C0001","Another system","Other",source="B")
        self.assertEqual(len(list_dtc(self.db,self.vid)),2)

    def test_linked_document_procedure_vehicle_ownership(self):
        procedure=create_procedure(self.db,self.vid,"DEMO","Synthetic procedure",source="TEST")
        article=self.db.add_article(self.vid,"Diagnosticare / DTC","Synthetic article","","TEST")
        pid_other=create_procedure(self.db,self.other,"DEMO","Other procedure",source="TEST")
        article_other=self.db.add_article(self.other,"Note atelier","Other article","","TEST")
        ident=add_dtc(self.db,self.vid,"P0A12","TEST","TEST",source="TEST",
                      procedure_id=procedure,article_id=article)
        self.assertEqual(list_dtc(self.db,self.vid)[0]["article_title"],"Synthetic article")
        self.assertIn("PROCEDURĂ ASOCIATĂ",dtc_text(self.db,ident))
        for kwargs in ({"procedure_id":pid_other},{"article_id":article_other}):
            with self.assertRaises(ValueError):
                add_dtc(self.db,self.vid,"P0A13","TEST","TEST",source="TEST",**kwargs)
        self.db.delete_article(article)
        self.assertIsNone(get_dtc(self.db,ident)["article_id"])
        self.db.delete_vehicle(self.vid)
        self.assertEqual(len(list_dtc(self.db)),0)
        self.assertEqual(self.db.db.execute("PRAGMA foreign_key_check").fetchall(),[])

    def test_import_export_idempotence_and_reject_bad_row(self):
        records=[{"make":"DEMO MAKE","model":"Model F","engine":"TEST MOTOR","years":"N/A",
                  "code":"P0ABC","system":"DEMO SYSTEM","title":"FAKE CODE","source":"FAKE TEST"}]
        path=self.root/"dtc.json"
        path.write_text(json.dumps({"schema":"atelierdata-dtc-v1","records":records}),encoding="utf-8")
        self.assertEqual(import_dtc(self.db,path)["inserted"],1)
        self.assertEqual(import_dtc(self.db,path)["duplicates"],1)
        export=self.root/"export.json"
        self.assertEqual(export_dtc(self.db,export),1)
        self.assertEqual(json.loads(export.read_text(encoding="utf-8"))["records"][0]["code"],"P0ABC")
        records.append(dict(records[0],code="P0A13",source=""))
        path.write_text(json.dumps(records),encoding="utf-8")
        with self.assertRaises(ValueError):
            import_dtc(self.db,path)
        self.assertEqual(len(list_dtc(self.db)),1)

    def test_csv_import_and_safety(self):
        path=self.root/"test.csv"
        path.write_text("make,model,engine,code,system,title,source\n"
                        "Demo,Car,X,P0A01,Example,Test only,Synthetic\n",encoding="utf-8")
        self.assertEqual(import_dtc(self.db,path)["inserted"],1)
        with self.assertRaises(ValueError):
            export_dtc(self.db,self.db.path)
        self.assertEqual(self.db.db.execute("PRAGMA quick_check").fetchone()[0],"ok")


if __name__=="__main__":
    unittest.main()
