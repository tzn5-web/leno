"""Synthetic only tests. No real automotive specs are distributed."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from atelierdata import Store
from technical_specs import (ensure_schema,add_spec,update_spec,remove_spec,get_spec,
                             list_specs,import_specs,export_specs)

class TechnicalSpecsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=Store(self.root/"test.sqlite3")
        self.addCleanup(self.store.close)
        ensure_schema(self.store)
        self.vehicle=self.store.add_vehicle("Example","Model X","FAKE-MOTOR","TEST","","")
    def test_create_update_search_and_cascade(self):
        ident=add_spec(self.store,self.vehicle,"Fictiv","Parametru exemplu","123","unit",
                       "Condiții fictive","TEST — NU FOLOSI ÎN REPARAȚII")
        self.assertEqual(add_spec(self.store,self.vehicle,"Fictiv","Parametru exemplu","123","unit",
                                  "Condiții fictive","TEST — NU FOLOSI ÎN REPARAȚII"),ident)
        self.assertEqual(len(list_specs(self.store,self.vehicle,search="exemplu")),1)
        update_spec(self.store,ident,"Fictiv","Revizuit","456","unit","","TEST")
        self.assertEqual(get_spec(self.store,ident)["parameter"],"Revizuit")
        self.store.delete_vehicle(self.vehicle)
        self.assertEqual(list_specs(self.store),[])

    def test_import_idempotent_and_atomic_validation(self):
        payload={"schema":"atelierdata-specifications-v1","specifications":[{
            "make":"Example","model":"Model X","engine":"FAKE-MOTOR","years":"TEST",
            "fuel":"","variant":"","system":"Fictiv","parameter":"Test-param",
            "value":"UNDEFINED","unit":"","conditions":"","source":"TEST_ONLY"}]}
        p=self.root/"import.json"
        p.write_text(json.dumps(payload),encoding="utf-8")
        self.assertEqual(import_specs(self.store,p)["inserted"],1)
        self.assertEqual(import_specs(self.store,p)["duplicates"],1)
        self.assertEqual(len(list_specs(self.store)),1)
        exp=self.root/"export.json"
        self.assertEqual(export_specs(self.store,exp),1)
        self.assertEqual(json.loads(exp.read_text(encoding="utf-8"))["specifications"][0]["source"],"TEST_ONLY")
        payload["specifications"].append(dict(payload["specifications"][0],source="",parameter="Bad"))
        payload["specifications"][0]["parameter"]="Another"
        p.write_text(json.dumps(payload),encoding="utf-8")
        with self.assertRaises(ValueError):import_specs(self.store,p)
        self.assertEqual(len(list_specs(self.store)),1)

    def test_missing_vehicle_source_and_invalid_files(self):
        with self.assertRaises(ValueError):
            add_spec(self.store,987,"System","Param","value",source="TEST_ONLY")
        with self.assertRaises(ValueError):
            add_spec(self.store,self.vehicle,"System","Param","value")
        with self.assertRaises(ValueError):
            export_specs(self.store,self.store.path)
        self.assertFalse(self.store.db.execute("PRAGMA foreign_key_check").fetchall())

    def test_search_literal_sql_wildcards_and_input_validation(self):
        for token in ("100%", "sensor_1", "back\\slash", "plain"):
            add_spec(self.store, self.vehicle, "Synthetic", token, "unknown",
                     source="SYNTHETIC")
        for token in ("100%", "sensor_1", "back\\slash", "plain"):
            results = list_specs(self.store, self.vehicle, search=token)
            self.assertEqual([row["parameter"] for row in results], [token])
        self.assertEqual(list_specs(self.store, self.vehicle, search="nonexistent"), [])
        for invalid in (None, 3, "x" * 201, "a\0b"):
            with self.assertRaises(ValueError):
                list_specs(self.store, self.vehicle, search=invalid)

    def test_import_csv(self):
        p=self.root/"import.csv"
        p.write_text("make,model,engine,years,system,parameter,value,source\n"
                     "Other,Test,FAKE,,Test,Test-param,TEST_VALUE,SYNTHETIC\n",encoding="utf-8")
        report=import_specs(self.store,p)
        self.assertEqual(report["inserted"],1)
        self.assertEqual(list_specs(self.store)[0]["make"],"Other")

if __name__=="__main__":unittest.main()
