"""Tests use only synthetic vPIC API responses; no network and no real VINs."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from atelierdata import Store
from vpic_catalog import (endpoint,parse_response,fetch_models,ensure_schema,
                          cache_models,cached_models,SOURCE)

def response(make="MITSUBISHI",year=2008):
    return json.dumps({"Count":3,"Message":"Response returned successfully",
        "Results":[
         {"Make_ID":514,"Make_Name":make,"Model_ID":1200,"Model_Name":"Lancer"},
         {"Make_ID":514,"Make_Name":make,"Model_ID":1201,"Model_Name":"Outlander"},
         {"Make_ID":91,"Make_Name":"OTHER MAKE","Model_ID":101,"Model_Name":"False match"}
        ]})

class VpicCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Store(Path(self.tmp.name)/"catalog.sqlite3")
        self.addCleanup(self.db.close)
        ensure_schema(self.db)

    def test_query_url_and_validation(self):
        self.assertIn("modelyear/2008?format=json",endpoint("MITSUBISHI",2008))
        with self.assertRaises(ValueError):endpoint("https://evil.org",2008)
        with self.assertRaises(ValueError):endpoint("MITSUBISHI",1900)
        with self.assertRaises(ValueError):endpoint("MITSUBISHI",False)
        with self.assertRaises(ValueError):endpoint("../etc/passwd",2008)

    def test_mock_fetch_exact_make_only(self):
        seen=[]
        def fixture(url):
            seen.append(url)
            return response()
        models=fetch_models("MITSUBISHI",2008,fetcher=fixture)
        self.assertEqual(len(seen),1)
        self.assertEqual(len(models),2)
        self.assertEqual({r["model_name"] for r in models},{"Lancer","Outlander"})
        self.assertEqual([r["model_year"] for r in models],[2008,2008])

    def test_offline_cache_and_no_personal_vehicle_mutation(self):
        models=parse_response(response(),"MITSUBISHI",2008)
        self.assertEqual(cache_models(self.db,models),2)
        self.assertEqual(cache_models(self.db,models),2)
        self.assertEqual(len(cached_models(self.db,"MITSUBISHI",2008)),2)
        self.assertEqual(self.db.stats()[0],0)
        self.assertEqual(cached_models(self.db,"MITSUBISHI",2009),[])
        self.assertEqual(cached_models(self.db,"FORD",2008),[])
        one=cached_models(self.db,"MITSUBISHI",2008)[0]
        self.assertEqual(one["source"],SOURCE)

    def test_reject_corrupt_response_and_atomic_invalid_cache(self):
        for invalid in ({"Results":None},{"Message":"error", "Results":[]},
                        {"Results":[{"not":"a model"}]*2501}):
            with self.assertRaises(ValueError):
                parse_response(invalid,"MITSUBISHI",2008)
        model=parse_response(response(),"MITSUBISHI",2008)[0]
        with self.assertRaises(ValueError):
            cache_models(self.db,[model,dict(model,model_name="x"*121)])
        self.assertEqual(len(cached_models(self.db,"MITSUBISHI",2008)),0)

if __name__=="__main__":
    unittest.main()
