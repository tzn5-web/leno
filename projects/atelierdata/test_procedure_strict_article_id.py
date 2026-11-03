"""Regression: article references reject coerced integer subclasses.

Synthetic fixture only; no licensed vehicle specifications.
"""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step, list_steps


class StrictArticleReferenceTests(unittest.TestCase):
    def test_subclassed_integer_reference_is_rejected_without_writes(self):
        class ForgedArticleId(int):
            pass

        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "article-id.sqlite3")
            try:
                vehicle = store.add_vehicle("SYNTHETIC", "MODEL")
                procedure = create_procedure(store, vehicle, "TEST", "REFERENCE",
                                             source="SYNTHETIC")
                before = store.db.total_changes
                for invalid in (True, False, 1.0, ForgedArticleId(1), -1, "1.0"):
                    with self.subTest(value=repr(invalid)):
                        with self.assertRaises(ValueError):
                            add_step(store, procedure, "Synthetic step", article_id=invalid)
                self.assertEqual(list_steps(store, procedure), [])
                self.assertEqual(store.db.total_changes, before)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
