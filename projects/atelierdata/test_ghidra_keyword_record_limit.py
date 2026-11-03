"""Synthetic regression for non-IDF keyword record limits."""
import unittest
from unittest import mock

from ghidra_idf_api_correlation import correlate
from test_ghidra_idf_api_correlation import fixtures, SHA


class KeywordRecordLimitTests(unittest.TestCase):
    def test_unrelated_keywords_cannot_bypass_record_cap(self):
        idf, api = fixtures()
        idf["keyword_hits"] = {".rdata": {
            "OTHER_A:ascii": [],
            "OTHER_B:ascii": [],
            "OTHER_C:ascii": [],
        }}
        with mock.patch("ghidra_idf_api_correlation.MAX_ITEMS", 2):
            with self.assertRaisesRegex(ValueError, "Too many IDF keyword records"):
                correlate(idf, api, SHA)

    def test_limit_allows_exact_number_of_keyword_entries(self):
        idf, api = fixtures()
        idf["keyword_hits"] = {".rdata": {
            "OTHER_A:ascii": [],
            "OTHER_B:ascii": [],
        }}
        with mock.patch("ghidra_idf_api_correlation.MAX_ITEMS", 2):
            result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_reference_count"], 0)
        self.assertFalse(result["idf_decoder_proven"])


if __name__ == "__main__":
    unittest.main()
