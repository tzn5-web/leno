"""Synthetic verification of workshop atlas facts and vehicle-scoped diagram pins."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from atelierdata import Store
from atelierdata_extensions import attach_document,resolve_document
from atelierdata_backup import backup_bundle,restore_bundle
from workshop_atlas import (ensure_schema,record_fact,list_facts,delete_fact,
                            add_marker,list_markers,delete_marker)

class WorkshopAtlasTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.store=Store(self.root/"atelierdata.sqlite3")
        self.addCleanup(self.store.close)
        self.m=self.store.add_vehicle("Mitsubishi","Lancer","4A91","2008","Benzină")
        self.o=self.store.add_vehicle("Opel","Astra","Z16XER","2010","Benzină")
        source=self.root/"owned.png"
        # Existing attachment storage hash verification needs no image decoder.
        source.write_bytes(b"\x89PNG\r\n\x1a\nSYNTHETIC-ONLY")
        self.article=self.store.add_article(self.m,"Scheme electrice","Test schematic","", "TEST ONLY")
        self.attachment=attach_document(self.store,self.article,source)

    def fact(self,**kwargs):
        data=dict(vehicle_id=self.m,kind="Cuplu de strângere",system="Motor",
                  component="Synthetic test fastener",source_name="TEST FIXTURE",
                  value="25",unit="Nm",stages="Faza 1: sintetic",
                  conditions="Numai test; nu folosi pe vehicul real",
                  attachment_id=self.attachment,page_number=1)
        data.update(kwargs)
        return record_fact(self.store,**data)

    def test_torque_stage_condition_and_exact_engine(self):
        id=self.fact()
        row=list_facts(self.store,self.m)[0]
        self.assertEqual(row["id"],id)
        self.assertEqual(row["engine"],"4A91")
        self.assertEqual(row["stages"],"Faza 1: sintetic")
        self.assertEqual(row["value"],"25")
        self.assertEqual(row["unit"],"Nm")
        self.assertEqual(row["page_number"],1)
        self.assertEqual(len(list_facts(self.store,self.o)),0)

    def test_torque_without_unit_rejected(self):
        with self.assertRaisesRegex(ValueError,"valoare și unitate"):
            self.fact(unit="")
        self.assertEqual(len(list_facts(self.store,self.m)),0)

    def test_location_needs_description(self):
        with self.assertRaisesRegex(ValueError,"Locația"):
            self.fact(kind="Locație componentă",value="",unit="")
        id=self.fact(kind="Locație componentă",value="",unit="",
                     component_location="Compartimentul motor (test)")
        self.assertEqual(list_facts(self.store,self.m)[0]["id"],id)

    def test_cross_vehicle_document_reference_rejected(self):
        with self.assertRaisesRegex(ValueError,"motorizării"):
            self.fact(vehicle_id=self.o)
        with self.assertRaisesRegex(ValueError,"motorizării"):
            add_marker(self.store,self.o,self.attachment,1,.2,.2,"X")

    def test_invalid_page_and_unlinked_page(self):
        with self.assertRaises(ValueError):self.fact(page_number=0)
        with self.assertRaises(ValueError):self.fact(attachment_id=None,page_number=2)

    def test_markers_coordinates_and_references(self):
        fid=self.fact()
        mid=add_marker(self.store,self.m,self.attachment,1,.25,.70,
                       "Conector test","Poziție sintetică",fid)
        row=list_markers(self.store,self.m,self.attachment,1)[0]
        self.assertEqual(row["id"],mid)
        self.assertEqual(row["fact_id"],fid)
        self.assertEqual(row["x"],.25)
        for x,y in ((-0.1,0.5),(0.5,1.1),(float("nan"),0.3)):
            with self.assertRaises(ValueError):
                add_marker(self.store,self.m,self.attachment,1,x,y,"BAD")
        with self.assertRaises(ValueError):
            add_marker(self.store,self.m,self.attachment,0,.1,.1,"BAD")
        with self.assertRaises(ValueError):
            add_marker(self.store,self.m,self.attachment,1,.1,.1,"WRONG",fact_id=99999)
        delete_marker(self.store,self.m,mid)
        self.assertEqual(list_markers(self.store,self.m,self.attachment,1),[])

    def test_edit_and_delete_are_vehicle_scoped(self):
        fid=self.fact()
        with self.assertRaises(ValueError):
            self.fact(vehicle_id=self.o,attachment_id=None,page_number=None,fact_id=fid)
        with self.assertRaises(ValueError):
            delete_fact(self.store,self.o,fid)
        changed=self.fact(fact_id=fid,value="40")
        self.assertEqual(changed,fid)
        self.assertEqual(list_facts(self.store,self.m)[0]["value"],"40")
        delete_fact(self.store,self.m,fid)
        self.assertEqual(list_facts(self.store,self.m),[])

    def test_backup_preserves_torque_and_diagram_pin(self):
        fid=self.fact()
        add_marker(self.store,self.m,self.attachment,1,.2,.4,"Synthetic",fact_id=fid)
        bundle=self.root/"bundle.zip"
        backup_bundle(self.store,bundle)
        target=restore_bundle(bundle,self.root/"restored")
        reopened=Store(target)
        try:
            ensure_schema(reopened)
            self.assertEqual(len(list_facts(reopened,self.m)),1)
            self.assertEqual(len(list_markers(reopened,self.m,self.attachment,1)),1)
            self.assertTrue(resolve_document(reopened,self.attachment).exists())
        finally:reopened.close()

    def test_delete_fact_keeps_pin_without_dangling_reference(self):
        fid=self.fact()
        mid=add_marker(self.store,self.m,self.attachment,1,.1,.1,"PIN",fact_id=fid)
        delete_fact(self.store,self.m,fid)
        row=list_markers(self.store,self.m,self.attachment,1)[0]
        self.assertEqual(row["id"],mid)
        self.assertIsNone(row["fact_id"])

    def test_literal_search_and_source(self):
        self.fact(component="Valve %_literal")
        self.assertEqual(len(list_facts(self.store,self.m,search="%_literal")),1)
        self.assertEqual(len(list_facts(self.store,self.m,search="%_mismatch")),0)
        self.assertEqual(len(list_facts(self.store,self.m,kind="Cuplu de strângere")),1)

if __name__=="__main__":unittest.main()
