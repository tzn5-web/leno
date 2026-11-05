"""Regression checks for document picker labels sourced from SQLite."""
import inspect
import unittest

from repair_procedures_gui import _safe_search_preview, open_procedures_window


class ReferencePickerLabelTests(unittest.TestCase):
    def test_untrusted_reference_metadata_is_single_line_and_bounded(self):
        for limit in (170, 280, 250):
            value = "Licensed\u2028source\u202e\n" + "X" * 400
            result = _safe_search_preview(value, limit)
            self.assertLessEqual(len(result), limit)
            self.assertNotIn("\n", result)
            self.assertNotIn("\u2028", result)
            self.assertNotIn("\u202e", result)

    def test_picker_sanitizes_all_sqlite_metadata_columns(self):
        source = inspect.getsource(open_procedures_window)
        for column, limit in (("category", 170), ("title", 280), ("source", 250)):
            self.assertIn(
                f'_safe_search_preview(article["{column}"], {limit})', source
            )


if __name__ == "__main__":
    unittest.main()
