"""Synthetic regression tests for Autodata-style vehicle service card."""
import tempfile
import unittest
from pathlib import Path
from atelierdata import Store
from atelierdata_backup import backup_bundle,restore_bundle
from vehicle_service_card import FIELD_DATA,card,add_value,edit_value,delete_value,SECTIONS

class ServiceCardTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.db=Store(self.root/"database.sqlite3")
        self.addCleanup(self.db.close)
        self.m=self.db.add_vehicle("Mitsubishi","Lancer","4A91","2008","Benzină")
        self.n=self.db.add_vehicle("Nissan","Micra","CR12DE","2006","Benzină")

    def field(self,section,label):
        return next(i for i,row in enumerate(FIELD_DATA) if tuple(row[:2])==(section,label))

    def test_all_categories_available_without_invented_specs(self):
        profile=card(self.db,self.m)
        self.assertIn("Antigel",SECTIONS)
        self.assertIn("Anvelope și roți",SECTIONS)
        self.assertIn("Ulei motor",SECTIONS)
        self.assertIn("Transmisie",SECTIONS)
        self.assertEqual(profile["sourced_count"],0)
        self.assertEqual(profile["values"][0][0]["value"],"4A91")
        self.assertIsNone(profile["values"][0][0]["id"])
        i=self.field("Antigel","Tip / omologare antigel")
        self.assertEqual(profile["values"][i],[])

    def test_sourced_oil_coolant_tyre_records(self):
        # All values in this test are synthetic and NOT recommendations for a car.
        for section,label,value,unit in (
            ("Ulei motor","Vâscozitate SAE","TEST-5W-30",""),
            ("Antigel","Tip / omologare antigel","TEST-SPEC-ABC",""),
            ("Anvelope și roți","Anvelope față","TEST-195/65 R15",""),
            ("Anvelope și roți","Presiune față normal","TEST-2.2","bar")):
            i=self.field(section,label)
            add_value(self.db,self.m,i,value,"DOCUMENT SINTETIC TEST pagina 1",
                      unit=unit,conditions="DOAR TEST")
            self.assertEqual(card(self.db,self.m)["values"][i][0]["value"],value)
        self.assertEqual(card(self.db,self.m)["sourced_count"],4)
        self.assertEqual(card(self.db,self.n)["sourced_count"],0)

    def test_same_parameter_has_distinct_sourced_variants(self):
        i=self.field("Anvelope și roți","Anvelope față")
        add_value(self.db,self.m,i,"TEST-A","test source A",conditions="config A")
        add_value(self.db,self.m,i,"TEST-B","test source B",conditions="config B")
        result=card(self.db,self.m)["values"][i]
        self.assertEqual(len(result),2)
        self.assertEqual({r["conditions"] for r in result},{"config A","config B"})

    def test_unknown_values_and_empty_sources_blocked(self):
        i=self.field("Ulei motor","Normă ACEA / API / OEM")
        with self.assertRaises(ValueError):add_value(self.db,self.m,i,"","manual")
        with self.assertRaises(ValueError):add_value(self.db,self.m,i,"TEST","")
        with self.assertRaises(ValueError):add_value(self.db,self.m,-1,"TEST","source")
        self.assertEqual(card(self.db,self.m)["sourced_count"],0)

    def test_cross_vehicle_edits_blocked(self):
        i=self.field("Antigel","Capacitate circuit")
        id=add_value(self.db,self.m,i,"TEST-5.0","test manual",unit="L")
        with self.assertRaisesRegex(ValueError,"alt vehicul"):
            edit_value(self.db,self.n,id,i,"TEST-6","manual")
        with self.assertRaisesRegex(ValueError,"alt vehicul"):
            delete_value(self.db,self.n,id)
        edit_value(self.db,self.m,id,i,"TEST-5.5","new test manual",unit="L")
        self.assertEqual(card(self.db,self.m)["values"][i][0]["value"],"TEST-5.5")
        delete_value(self.db,self.m,id)
        self.assertEqual(card(self.db,self.m)["values"][i],[])

    def test_existing_technical_specs_are_included(self):
        from technical_specs import add_spec
        id=add_spec(self.db,self.m,"Răcire","Tip antigel","TEST COOLANT","",
                    "synthetic condition","synthetic source")
        i=self.field("Antigel","Tip / omologare antigel")
        self.assertEqual(card(self.db,self.m)["values"][i][0]["id"],id)

    def test_backup_preserves_vehicle_card(self):
        i=self.field("Anvelope și roți","Anvelope spate")
        add_value(self.db,self.m,i,"TEST-205/55R16","test source")
        filename=self.root/"backup.zip"
        backup_bundle(self.db,filename)
        restored=Store(restore_bundle(filename,self.root/"restored"))
        try:self.assertEqual(card(restored,self.m)["values"][i][0]["value"],"TEST-205/55R16")
        finally:restored.close()

if __name__=="__main__":unittest.main()
