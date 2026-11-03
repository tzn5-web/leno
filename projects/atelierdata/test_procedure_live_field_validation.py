"""Reject malformed live-search labels without accessing SQLite."""
import unittest
from types import SimpleNamespace

from procedure_search_live import validate_live_hit


class NoDatabaseAccess:
    def execute(self, *args, **kwargs):
        raise AssertionError("Malformed hit reached SQLite")


class LiveSearchFieldValidationTests(unittest.TestCase):
    def test_non_string_labels_fail_closed_before_sql(self):
        store = SimpleNamespace(db=NoDatabaseAccess())
        for label in (None, [], {}, ["Titlu"], 1, True):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, "Invalid search field"):
                    validate_live_hit(
                        store, 1,
                        {"procedure_id": 1, "field": label},
                        "needle",
                    )


if __name__ == "__main__":
    unittest.main()
