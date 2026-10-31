"""Checks provider references stay offline, vehicle-scoped, accurate and deduplicated."""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from technical_source_references import save_source_reference

class SourceReferenceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db=Store(Path(tmp.name)/"data.sqlite3")
        self.addCleanup(self.db.close)
        self.a=self.db.add_vehicle("Mitsubishi","Lancer","4A91","2008","Benzina")
        self.b=self.db.add_vehicle("Opel","Astra","Z16XER","2009","Benzina")

    def test_source_bookmark_exact_vehicle(self):
        row=save_source_reference(self.db,self.a,"mmc_lancer")
        self.assertTrue(row["created"])
        article=self.db.get_article(row["article_id"])
        self.assertIn("Referință online",article["title"])
        self.assertIn("4A91",self.db.db.execute("SELECT engine FROM vehicles WHERE id=?",(self.a,)).fetchone()[0])
        self.assertEqual(article["source"],"https://www.mmc-manuals.ru/Mitsubishi_Lancer_X%3A_Service_Manuals")
        self.assertIn("nu conține date tehnice importate",article["content"])
        self.assertEqual(self.db.db.execute("SELECT COUNT(*) FROM attachments").fetchone()[0],0)

    def test_dedup(self):
        x=save_source_reference(self.db,self.a,"mmc_lancer")
        y=save_source_reference(self.db,self.a,"mmc_lancer")
        self.assertEqual(x["article_id"],y["article_id"])
        self.assertFalse(y["created"])
        self.assertEqual(self.db.stats()[1],1)

    def test_unsupported_make_rejected(self):
        with self.assertRaisesRegex(ValueError,"marca"):
            save_source_reference(self.db,self.b,"mmc_lancer")
        self.assertEqual(self.db.stats()[1],0)

    def test_link_allows_generic_obd_source(self):
        x=save_source_reference(self.db,self.a,"androbd")
        y=save_source_reference(self.db,self.b,"androbd")
        self.assertNotEqual(x["article_id"],y["article_id"])

    def test_missing_source_or_vehicle_fails(self):
        for vid,key in ((999,"mmc_lancer"),(self.a,"source_does_not_exist")):
            with self.assertRaises(ValueError):
                save_source_reference(self.db,vid,key)

if __name__=="__main__":
    unittest.main()
