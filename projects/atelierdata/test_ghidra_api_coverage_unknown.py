"""Synthetic regression: missing API scan-cap flag cannot prove coverage."""
import unittest
from ghidra_idf_api_correlation import correlate

SHA = "a" * 64

def evidence(with_flag):
    base = dict(source_sha256=SHA, idf_decoder_proven=False, target_executed=False)
    idf = dict(base, keyword_hits={"b": {"SYNTHETIC.IDF:utf16le": [
        {"references_from": [{"function_entry": "RAM:00401000"}]}]}},
        block_scan_cap_reached=False, keyword_match_cap_reached=False,
        keyword_xref_cap_reached=False, short_memory_read=False,
        keyword_scan_coverage_complete=True)
    ref = {"function_entry": "RAM:00401000",
           "reference_type": "UNCONDITIONAL_CALL",
           "reference_is_call_or_jump": True}
    api = dict(base, schema="atelierdata-ghidra-file-api-xrefs-v1",
               api_symbols={"CreateFileW": [{"references": [ref]}],
                            "ReadFile": [{"references": [ref]}]})
    if with_flag:
        api["symbol_scan_truncated"] = False
    return idf, api

class ApiCoverageUnknownTests(unittest.TestCase):
    def test_missing_flag_fails_closed_without_losing_raw_candidate(self):
        result = correlate(*evidence(False), SHA)
        self.assertFalse(result["api_scan_coverage_known"])
        self.assertEqual(result["shared_idf_and_file_open_and_read_call_or_jump_functions"], 1)
        self.assertFalse(result["static_triage_coverage_adequate"])
        self.assertFalse(result["open_read_idf_triage_candidate_with_complete_coverage"])
        self.assertFalse(result["direct_file_io_triage_candidate_with_complete_coverage"])

    def test_explicit_nontruncated_flag_allows_strict_triage(self):
        result = correlate(*evidence(True), SHA)
        self.assertTrue(result["api_scan_coverage_known"])
        self.assertTrue(result["static_triage_coverage_adequate"])
        self.assertTrue(result["open_read_idf_triage_candidate_with_complete_coverage"])

if __name__ == "__main__":
    unittest.main()
