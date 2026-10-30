"""Only synthetic test procedures; no actual safety-critical instructions."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from atelierdata import Store
from repair_procedures import (ensure_schema,create_procedure,update_procedure,
    get_procedure,list_procedures,delete_procedure,add_step,update_step,delete_step,
    move_step,list_steps,procedure_text)

class ProcedureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=Store(self.root/"test.sqlite3")
        self.addCleanup(self.db.close)
        ensure_schema(self.db)
        self.vid=self.db.add_vehicle("TEST BRAND","TEST MODEL","DEMO-ONLY")
        self.other=self.db.add_vehicle("SECOND TEST","MODEL","DEMO-ONLY")
        self.pid=create_procedure(self.db,self.vid,"Sistem fictiv","Exercițiu",
              "Doar test","Nu folosi pentru reparații","Date sintetice de test")

    def test_add_move_insert_and_delete_steps(self):
        first=add_step(self.db,self.pid,"Pas imaginar 1")
        third=add_step(self.db,self.pid,"Pas imaginar 3",safety_note="Notă test")
        middle=add_step(self.db,self.pid,"Pas imaginar 2",position=2)
        rows=list_steps(self.db,self.pid)
        self.assertEqual([r["id"] for r in rows],[first,middle,third])
        self.assertEqual([r["step_number"] for r in rows],[1,2,3])
        self.assertTrue(move_step(self.db,third,-1))
        self.assertEqual([r["id"] for r in list_steps(self.db,self.pid)],[first,third,middle])
        self.assertFalse(move_step(self.db,first,-1))
        delete_step(self.db,third)
        self.assertEqual([r["step_number"] for r in list_steps(self.db,self.pid)],[1,2])
        self.assertFalse(self.db.db.execute("PRAGMA foreign_key_check").fetchall())

    def test_document_link_same_vehicle_only(self):
        document=self.db.add_article(self.vid,"Scheme electrice","Diagramă demo",
                                "Nu este o schemă reală","Date test")
        elsewhere=self.db.add_article(self.other,"Scheme electrice","Alt demo","Test","Test")
        sid=add_step(self.db,self.pid,"Citește desenul de test",article_id=document)
        self.assertEqual(list_steps(self.db,self.pid)[0]["reference_title"],"Diagramă demo")
        with self.assertRaises(ValueError):
            add_step(self.db,self.pid,"Greșit",article_id=elsewhere)
        with self.assertRaises(ValueError):
            update_step(self.db,sid,"Greșit",article_id=elsewhere)
        update_step(self.db,sid,"Pas revizuit",article_id=document)
        self.assertIn("DOCUMENT ASOCIAT",procedure_text(self.db,self.pid))
        self.db.delete_article(document)
        self.assertIsNone(list_steps(self.db,self.pid)[0]["article_id"])

    def test_procedure_provenance_and_vehicle_cascade(self):
        self.assertEqual(get_procedure(self.db,self.pid)["source"],"Date sintetice de test")
        self.assertEqual(len(list_procedures(self.db,self.vid,search="Exercițiu")),1)
        update_procedure(self.db,self.pid,"Sistem 2","Titlu nou",source="SURSĂ DEMO")
        self.assertIn("SURSĂ DEMO",procedure_text(self.db,self.pid))
        add_step(self.db,self.pid,"Acțiune demo")
        self.db.delete_vehicle(self.vid)
        self.assertEqual(list_procedures(self.db),[])
        self.assertEqual(self.db.db.execute("SELECT COUNT(*) FROM procedure_steps").fetchone()[0],0)

    def test_reject_invalid_and_missing_source(self):
        with self.assertRaises(ValueError):
            create_procedure(self.db,self.vid,"Test","Title")
        with self.assertRaises(ValueError):
            create_procedure(self.db,10**8,"Test","Title",source="Test")
        with self.assertRaises(ValueError):
            add_step(self.db,self.pid,"")
        with self.assertRaises(ValueError):
            add_step(self.db,self.pid,"Step",position=2)
        with self.assertRaises(ValueError):
            move_step(self.db,999,-1)
        self.assertEqual(len(list_steps(self.db,self.pid)),0)

    def test_reopen_and_integrity(self):
        add_step(self.db,self.pid,"Pas 1")
        self.db.close()
        reopened=Store(self.root/"test.sqlite3")
        try:
            ensure_schema(reopened)
            self.assertEqual(len(list_steps(reopened,self.pid)),1)
            self.assertEqual(reopened.db.execute("PRAGMA quick_check").fetchone()[0],"ok")
        finally:
            reopened.close()

if __name__=="__main__":
    unittest.main()
