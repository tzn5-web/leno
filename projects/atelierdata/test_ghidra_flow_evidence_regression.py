"""Synthetic regression: data xrefs cannot prove an IDF/open/read call chain."""
import unittest
from ghidra_idf_api_correlation import correlate

SHA = "b" * 64
COVERAGE = dict(block_scan_cap_reached=False,
                keyword_match_cap_reached=False,
                keyword_xref_cap_reached=False,
                short_memory_read=False,
                keyword_scan_coverage_complete=True)


def reports(read_type="DATA", read_flow=False):
    identity = dict(source_sha256=SHA, idf_decoder_proven=False,
                    target_executed=False)
    idf = dict(identity, **COVERAGE, keyword_hits={
        "synthetic": {"EXAMPLE.IDF:ascii": [{
            "references_from": [{"function_entry": "RAM:00401000", "reference_target_provenance": "exact_match"}]
        }]}})
    def ref(kind, flow):
        return dict(function_entry="RAM:00401000",
                    reference_type=kind,
                    reference_is_call_or_jump=flow)
    api = dict(identity, schema="atelierdata-ghidra-file-api-xrefs-v1",
               symbol_scan_truncated=False,
               api_symbols={
                   "CreateFileW": [{"references": [
                       ref("UNCONDITIONAL_CALL", True)]}],
                   "ReadFile": [{"references": [ref(read_type, read_flow)]}]
               })
    return idf, api


class FlowEvidenceRegression(unittest.TestCase):
    def test_data_reference_to_readfile_is_not_a_call(self):
        result = correlate(*reports(), SHA)
        self.assertEqual(
            result["shared_idf_and_file_open_and_read_call_or_jump_functions"], 0)
        self.assertFalse(
            result["open_read_idf_triage_candidate_with_complete_coverage"])

    def test_real_flow_reference_is_only_triage(self):
        result = correlate(*reports("UNCONDITIONAL_CALL", True), SHA)
        self.assertEqual(
            result["shared_idf_and_file_open_and_read_call_or_jump_functions"], 1)
        self.assertTrue(
            result["open_read_idf_triage_candidate_with_complete_coverage"])
        self.assertFalse(result["idf_decoder_proven"])

    def test_contradictory_flow_metadata_rejected(self):
        with self.assertRaisesRegex(ValueError, "Contradictory"):
            correlate(*reports("DATA", True), SHA)


if __name__ == "__main__":
    unittest.main()
