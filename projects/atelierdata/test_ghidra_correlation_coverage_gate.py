"""Synthetic coverage-gate regression: no proprietary binaries or IDF data."""
import unittest
from ghidra_idf_api_correlation import correlate
from test_ghidra_idf_api_correlation import fixtures, SHA


class CoverageGateTests(unittest.TestCase):
    def complete(self):
        idf, api = fixtures()
        idf.update(block_scan_cap_reached=False,
                   keyword_match_cap_reached=False,
                   keyword_xref_cap_reached=False,
                   short_memory_read=False,
                   keyword_scan_coverage_complete=True)
        return idf, api

    def test_complete_owned_typed_evidence_allows_static_triage(self):
        idf, api = self.complete()
        result = correlate(idf, api, SHA)
        self.assertTrue(result["static_triage_coverage_adequate"])
        self.assertFalse(result["idf_decoder_proven"])

    def test_legacy_coverage_fails_closed(self):
        idf, api = fixtures()
        self.assertFalse(correlate(idf, api, SHA)["static_triage_coverage_adequate"])

    def test_api_truncation_fails_closed(self):
        idf, api = self.complete()
        api["symbol_scan_truncated"] = True
        self.assertFalse(correlate(idf, api, SHA)["static_triage_coverage_adequate"])

    def test_unowned_idf_reference_fails_closed(self):
        idf, api = self.complete()
        idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"].append(
            {"function_entry": None})
        self.assertFalse(correlate(idf, api, SHA)["static_triage_coverage_adequate"])

    def test_unknown_flow_fails_closed(self):
        idf, api = self.complete()
        api["api_symbols"]["ReadFile"][0]["references"][0].pop("reference_type")
        self.assertFalse(correlate(idf, api, SHA)["static_triage_coverage_adequate"])


if __name__ == "__main__":
    unittest.main()
