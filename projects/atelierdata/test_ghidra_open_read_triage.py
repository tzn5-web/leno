"""Synthetic-only tests for same-function IDF/open/read static triage."""
import unittest

from ghidra_idf_api_correlation import correlate

SHA = "a" * 64


def reports(read_function="RAM:00401000", complete=True):
    identity = dict(source_sha256=SHA, idf_decoder_proven=False,
                    target_executed=False)
    idf = dict(identity, keyword_hits={
        "block": {"SYNTHETIC.IDF:ascii": [
            {"references_from": [{"function_entry": "RAM:00401000", "reference_target_provenance": "exact_match"}]}
        ]}
    })
    if complete:
        idf.update(block_scan_cap_reached=False,
                   keyword_match_cap_reached=False,
                   keyword_xref_cap_reached=False,
                   short_memory_read=False,
                   keyword_scan_coverage_complete=True)
    def ref(fn):
        return {"function_entry": fn,
                "reference_type": "UNCONDITIONAL_CALL",
                "reference_is_call_or_jump": True}
    api = dict(identity, schema="atelierdata-ghidra-file-api-xrefs-v1",
               api_symbols={"CreateFileW": [{"references": [ref("RAM:00401000")]}],
                            "ReadFile": [{"references": [ref(read_function)]}]},
               symbol_scan_truncated=False)
    return idf, api


class OpenReadTriageTests(unittest.TestCase):
    def test_same_function_with_complete_coverage(self):
        result = correlate(*reports(), SHA)
        self.assertEqual(result["shared_idf_and_file_open_and_read_call_or_jump_functions"], 1)
        self.assertTrue(result["open_read_idf_triage_candidate_with_complete_coverage"])
        self.assertFalse(result["idf_decoder_proven"])

    def test_distinct_functions_do_not_count(self):
        result = correlate(*reports(read_function="RAM:00402000"), SHA)
        self.assertEqual(result["shared_idf_and_file_open_and_read_call_or_jump_functions"], 0)
        self.assertFalse(result["open_read_idf_triage_candidate_with_complete_coverage"])

    def test_unknown_coverage_is_not_complete(self):
        result = correlate(*reports(complete=False), SHA)
        self.assertEqual(result["shared_idf_and_file_open_and_read_call_or_jump_functions"], 1)
        self.assertFalse(result["open_read_idf_triage_candidate_with_complete_coverage"])


if __name__ == "__main__":
    unittest.main()
