"""Synthetic tests for strict private Ghidra JSON parsing (no original binaries)."""
import json
import tempfile
import unittest
from pathlib import Path

from ghidra_idf_api_correlation import load_private


class PrivateGhidraJSONTests(unittest.TestCase):
    def _load(self, payload):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "evidence.json"
            path.write_text(payload, encoding="utf-8")
            return load_private(path)

    def test_reject_nan(self):
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            self._load('{"references": [NaN]}')

    def test_reject_positive_infinity(self):
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            self._load('{"references": [Infinity]}')

    def test_reject_negative_infinity_nested(self):
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            self._load('{"references": [{"offset": -Infinity}]}')

    def test_accept_finite_json(self):
        self.assertEqual(self._load('{"references": [1.5, null, false]}'),
                         {"references": [1.5, None, False]})

    def test_reject_duplicate_nested_keys(self):
        with self.assertRaisesRegex(ValueError, "Duplicate key"):
            self._load('{"references": [{"a": 1, "a": 2}]}')


if __name__ == "__main__":
    unittest.main()
