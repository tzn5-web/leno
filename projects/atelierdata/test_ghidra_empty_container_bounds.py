"""Synthetic regression tests for bounded empty Ghidra containers."""
import unittest
from unittest import mock

from ghidra_idf_api_correlation import correlate
from test_ghidra_idf_api_correlation import fixtures, SHA


class EmptyContainerBoundsTests(unittest.TestCase):
    def test_empty_idf_blocks_cannot_bypass_limit(self):
        idf, api = fixtures()
        idf["keyword_hits"] = {f"section_{i}": {} for i in range(4)}
        with mock.patch("ghidra_idf_api_correlation.MAX_ITEMS", 3):
            with self.assertRaisesRegex(ValueError, "Too many Ghidra report containers"):
                correlate(idf, api, SHA)

    def test_empty_api_names_cannot_bypass_limit(self):
        idf, api = fixtures()
        api["api_symbols"] = {f"UnusedAPI{i}": [] for i in range(4)}
        with mock.patch("ghidra_idf_api_correlation.MAX_ITEMS", 3):
            with self.assertRaisesRegex(ValueError, "Too many Ghidra report containers"):
                correlate(idf, api, SHA)

    def test_exact_container_limit_is_accepted(self):
        idf, api = fixtures()
        idf["keyword_hits"] = {"first": {}, "second": {}, "third": {}}
        api["api_symbols"] = {"first": [], "second": [], "third": []}
        with mock.patch("ghidra_idf_api_correlation.MAX_ITEMS", 3):
            result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_reference_count"], 0)
        self.assertEqual(result["api_reference_count"], 0)
        self.assertFalse(result["idf_decoder_proven"])


if __name__ == "__main__":
    unittest.main()
