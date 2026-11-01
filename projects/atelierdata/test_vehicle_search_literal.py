"""Synthetic vehicle-search regressions: literal LIKE, input bounds and scope."""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store


class VehicleSearchLiteralTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "vehicles.sqlite3")
        self.percent = self.store.add_vehicle("100% Motors", "Alpha")
        self.underscore = self.store.add_vehicle("Maker", "A_B")
        self.slash = self.store.add_vehicle("Maker", r"A\B")
        self.plain = self.store.add_vehicle("Maker", "AXB")
        self.engine = self.store.add_vehicle("Maker", "Other", engine="E_10")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def ids(self, term):
        return {row["id"] for row in self.store.list_vehicles(term)}

    def test_percent_is_literal(self):
        self.assertEqual(self.ids("%"), {self.percent})

    def test_underscore_is_literal(self):
        self.assertEqual(self.ids("_"), {self.underscore, self.engine})
        self.assertEqual(self.ids("A_B"), {self.underscore})

    def test_backslash_is_literal(self):
        self.assertEqual(self.ids("\\"), {self.slash})

    def test_plain_text_unchanged(self):
        self.assertEqual(self.ids("AXB"), {self.plain})
        self.assertEqual(self.ids("E_10"), {self.engine})

    def test_empty_query_lists_all(self):
        self.assertEqual(len(self.store.list_vehicles()), 5)

    def test_invalid_types_and_size_rejected(self):
        for term in (None, 3, b"abc", "\0", "x" * 201):
            with self.subTest(term=repr(term)[:40]):
                with self.assertRaises(ValueError):
                    self.store.list_vehicles(term)


if __name__ == "__main__":
    unittest.main()
