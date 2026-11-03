"""Regression tests for strict pagination argument types in procedure search."""
import unittest
from unittest.mock import patch

from procedure_search_hits import list_procedure_hits


class IntSubclass(int):
    pass


class PaginationTypesTests(unittest.TestCase):
    def test_invalid_pagination_types_rejected_before_database_access(self):
        class NoDatabase:
            @property
            def db(self):
                raise AssertionError("database accessed for invalid pagination")

        store = NoDatabase()
        for limit, offset in (
            (IntSubclass(1), 0),
            (1, IntSubclass(0)),
            (True, 0),
            (1, False),
            (1.0, 0),
            (1, "0"),
        ):
            with self.subTest(limit=limit, offset=offset):
                with self.assertRaises(ValueError):
                    list_procedure_hits(store, 1, "sample", limit=limit, offset=offset)

    def test_valid_pagination_still_returns_empty_hits(self):
        class Store:
            pass

        with patch("procedure_search_hits.list_procedures", return_value=[]) as search:
            self.assertEqual(list_procedure_hits(Store(), 1, "sample", limit=1, offset=0), [])
            search.assert_called_once_with(unittest.mock.ANY, 1, "sample")


if __name__ == "__main__":
    unittest.main()
