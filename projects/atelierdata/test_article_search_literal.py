"""Regression tests: article search treats LIKE metacharacters literally."""
import tempfile
import unittest
from pathlib import Path
from atelierdata import Store


class ArticleSearchLiteralTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Store(Path(self.temp.name) / "search.sqlite3")
        self.v1 = self.db.add_vehicle("Test", "One")
        self.v2 = self.db.add_vehicle("Test", "Two")
        self.a_percent = self.db.add_article(self.v1, "Note atelier", "100% test", "literal % value")
        self.a_underscore = self.db.add_article(self.v1, "Motor", "P_0420", "sensor_A")
        self.a_plain = self.db.add_article(self.v1, "Motor", "P10420", "sensorBA")
        self.a_slash = self.db.add_article(self.v1, "Motor", r"test\module", "value")
        self.a_other = self.db.add_article(self.v2, "Motor", "P_0420", "another vehicle")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def ids(self, **kwargs):
        return {r["id"] for r in self.db.list_articles(**kwargs)}

    def test_percent_is_literal(self):
        self.assertEqual(self.ids(vid=self.v1, search="%"), {self.a_percent})

    def test_underscore_is_literal(self):
        self.assertEqual(self.ids(vid=self.v1, search="P_"), {self.a_underscore})
        self.assertEqual(self.ids(vid=self.v1, search="sensor_"), {self.a_underscore})

    def test_backslash_is_literal(self):
        self.assertEqual(self.ids(vid=self.v1, search="\\"), {self.a_slash})

    def test_category_and_vehicle_scope(self):
        self.assertEqual(self.ids(vid=self.v1, category="Motor", search="_"),
                         {self.a_underscore})
        self.assertEqual(self.ids(vid=self.v2, search="P_"), {self.a_other})

    def test_empty_search_keeps_existing_behavior(self):
        self.assertEqual(len(self.db.list_articles(vid=self.v1)), 4)

    def test_invalid_search_type(self):
        with self.assertRaises(ValueError):
            self.db.list_articles(search=None)


if __name__ == "__main__":
    unittest.main()
