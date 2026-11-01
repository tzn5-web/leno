"""Synthetic regression tests for bounded AtelierData CSV/JSON imports."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import import_validation
from atelierdata import Store, import_records


class ImportPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "test.sqlite3")
        self.addCleanup(self.store.close)

    def _json(self, records, **other):
        path = self.root / "records.json"
        path.write_text(json.dumps({"schema": "atelierdata-records-v1",
                                    "records": records, **other}), encoding="utf-8")
        return path

    def _csv(self, text):
        path = self.root / "records.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_json_schema_and_literal_values(self):
        path = self._json([{"make": "Mitsubishi", "model": "Lancer",
                            "category": "Note atelier", "title": "100%_literal",
                            "content": "Text utilizator", "source": "manual"}])
        self.assertEqual(import_records(self.store, path)["inserted"], 1)
        self.assertEqual(self.store.stats(), [1, 1])
        self.assertEqual(self.store.list_articles(search="100%_literal")[0]["title"],
                         "100%_literal")

    def test_valid_csv_unicode_and_optional_fields(self):
        path = self._csv("make,model,category,title,body\n"
                         "Dacia,Logan,Note atelier,Înregistrare,Exemplu propriu\n")
        self.assertEqual(import_records(self.store, path)["inserted"], 1)
        self.assertEqual(self.store.list_articles()[0]["content"], "Exemplu propriu")

    def test_invalid_json_row_does_not_partially_write(self):
        path = self._json([
            {"make": "A", "model": "B", "category": "C", "title": "Valid"},
            {"make": "A", "model": None, "category": "C", "title": "Invalid"},
        ])
        result = import_records(self.store, path)
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(len(result["rejected"]), 1)
        self.assertEqual(self.store.stats(), [0, 0])

    def test_nested_and_boolean_values_rejected_not_stringified(self):
        for value in ({"unexpected": "object"}, ["list"], True, 12):
            with self.subTest(value=value):
                path = self._json([{"make": "A", "model": "B",
                                    "category": "C", "title": "T",
                                    "content": value}])
                result = import_records(self.store, path)
                self.assertEqual(result["inserted"], 0)
                self.assertEqual(len(result["rejected"]), 1)
                self.assertEqual(self.store.stats(), [0, 0])

    def test_csv_duplicate_or_unknown_headers_fail_closed(self):
        for text in ("make,make,model,category,title\nA,B,C,D,E\n",
                     "make,model,category,title,typo\nA,B,C,D,E\n",
                     "make,model,category\nA,B,C\n",
                     "make,model,category,title\nA,B,C,D,EXTRA\n"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    import_records(self.store, self._csv(text))
                self.assertEqual(self.store.stats(), [0, 0])

    def test_json_schema_and_records_required(self):
        path = self.root / "records.json"
        for obj in ({"schema": "unknown", "records": []},
                    {"schema": "atelierdata-records-v1"},
                    {"schema": "atelierdata-records-v1", "records": {}},
                    123):
            with self.subTest(obj=obj):
                path.write_text(json.dumps(obj), encoding="utf-8")
                with self.assertRaises(ValueError):
                    import_records(self.store, path)

    def test_row_and_file_limits_reject_before_writes(self):
        path = self._json([{"make": "A", "model": "B",
                            "category": "C", "title": "T"}] * 3)
        with patch.object(import_validation, "MAX_IMPORT_ROWS", 2):
            with self.assertRaises(ValueError):
                import_records(self.store, path)
        with patch.object(import_validation, "MAX_IMPORT_BYTES", 10):
            with self.assertRaises(ValueError):
                import_records(self.store, path)
        self.assertEqual(self.store.stats(), [0, 0])

    def test_embedded_nul_and_overlong_title_rejected(self):
        for title in ("A\x00B", "T" * 501):
            path = self._json([{"make": "A", "model": "B",
                                "category": "C", "title": title}])
            result = import_records(self.store, path)
            self.assertEqual(result["inserted"], 0)
            self.assertEqual(len(result["rejected"]), 1)
        self.assertEqual(self.store.stats(), [0, 0])

    def test_symlink_input_rejected_when_supported(self):
        original = self._json([])
        alias = self.root / "alias.json"
        try:
            alias.symlink_to(original)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(ValueError):
            import_records(self.store, alias)


if __name__ == "__main__":
    unittest.main()
