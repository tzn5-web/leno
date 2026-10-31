"""Offline tests: curated source provenance, filters, access, no network I/O."""
import unittest
from dataclasses import replace
from technical_sources import SOURCES, Source, ALL, normalize, search_sources, validate_catalog, makes, categories
from technical_sources_gui import make_for_selected_vehicle, ACCESS_NAMES

class SourcesTests(unittest.TestCase):
    def test_catalog_unique_valid_https_provenance(self):
        self.assertTrue(validate_catalog())
        self.assertGreaterEqual(len(SOURCES),20)
        self.assertEqual(len({x.key for x in SOURCES}),len(SOURCES))
        self.assertTrue(all(x.url.startswith("https://") and x.provenance.startswith("https://") for x in SOURCES))

    def test_five_priority_makes_present(self):
        for name in ("Opel","Mitsubishi","BMW","Nissan","Skoda"):
            self.assertIn(name,makes())
            self.assertGreaterEqual(len(search_sources(make=name)),3)

    def test_free_vs_paid_does_not_mislabel_oem(self):
        by_key={x.key:x for x in SOURCES}
        self.assertEqual(by_key["skoda_erwin"].access,"cu_plata")
        self.assertEqual(by_key["bmw_aos"].access,"cu_plata")
        self.assertEqual(by_key["stellantis_servicebox"].access,"cu_plata")
        self.assertEqual(by_key["nissan_techinfo"].access,"mixt")
        self.assertEqual(by_key["charm"].access,"gratis")
        self.assertEqual(by_key["mmc_lancer"].access,"public_neoficial")

    def test_opel_does_not_claim_charm_or_bmw_manual(self):
        found={x.key for x in search_sources(make="Opel")}
        self.assertIn("autodoc",found)
        self.assertIn("stellantis_servicebox",found)
        self.assertNotIn("charm",found)
        self.assertNotIn("bmw_aos",found)

    def test_mitsubishi_4a91_keyword(self):
        # A keyword can also occur in a source's warning that the document
        # is NOT a workshop manual. Do not assume search results are service
        # procedures, and do not make this test brittle when sources grow.
        hits=search_sources(query="4A91",make="Mitsubishi")
        by_key={item.key:item for item in hits}
        self.assertIn("mmc_lancer",by_key)
        self.assertIn("mitsubishi_owners",by_key)
        owner=by_key["mitsubishi_owners"]
        self.assertIn("Manual utilizare",owner.categories)
        self.assertNotIn("Proceduri",owner.categories)
        self.assertNotIn("Scheme",owner.categories)
        self.assertIn("nu substitui",owner.notes.casefold())
        self.assertEqual(owner.access,"gratis")

    def test_category_and_access_filter(self):
        q=search_sources(make="Skoda",category="Proceduri",access="cu_plata")
        self.assertIn("skoda_erwin",{x.key for x in q})
        self.assertNotIn("autodoc",{x.key for x in q})
        self.assertIn("Scheme",categories())
        self.assertEqual(ACCESS_NAMES["gratis"],"Gratuit")

    def test_search_case_diacritics(self):
        self.assertEqual(normalize("ŠKODA"),"skoda")
        self.assertTrue(search_sources(query="Rômânia",make="Opel"))
        self.assertEqual(search_sources(make="NONEXISTENT"),[x for x in SOURCES if ALL in x.makes])

    def test_bad_urls_and_duplicates_rejected(self):
        first=SOURCES[0]
        with self.assertRaisesRegex(ValueError,"duplicate"):
            validate_catalog([first,first])
        for url in ("http://example.org/path","file:///tmp/x","https://127.0.0.1/a",
                    "https://user:pass@example.org"):
            with self.subTest(url=url),self.assertRaises(ValueError):
                validate_catalog([replace(first,url=url)])

    def test_selected_vehicle_make_does_not_network(self):
        class Store:
            def execute(self,sql,params):
                self.params=params
                return self
            def fetchone(self):
                return {"make":"Škoda"}
        class Db:
            db=Store()
        class App:
            vid=42
            db=Db()
        self.assertEqual(make_for_selected_vehicle(App()),"skoda")
        self.assertEqual(Db.db.params,(42,))

if __name__=="__main__":
    unittest.main()
