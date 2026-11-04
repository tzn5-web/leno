"""Synthetic provenance regression; no proprietary inputs."""
import unittest
from ghidra_idf_api_correlation import correlate

SHA = "a" * 64

def make_reports(provenances):
    identity = dict(source_sha256=SHA, idf_decoder_proven=False,
                    target_executed=False)
    idf = dict(identity,
               block_scan_cap_reached=False,
               keyword_match_cap_reached=False,
               keyword_xref_cap_reached=False,
               short_memory_read=False,
               keyword_scan_coverage_complete=True,
               keyword_hits={"synthetic": {"TEST.IDF:ascii": [{
                   "references_from": [
                       {"function_entry": "RAM:00401000", **(
                           {"reference_target_provenance": p} if p is not None else {}
                       )} for p in provenances]
               }]}})
    api = dict(identity, schema="atelierdata-ghidra-file-api-xrefs-v1",
               symbol_scan_truncated=False, api_symbols={})
    return idf, api

class IDFProvenanceRegression(unittest.TestCase):
    def test_exact_and_containing_xrefs_counted_separately(self):
        report = correlate(*make_reports(["exact_match", "containing_data_start"]), SHA)
        self.assertEqual(report["idf_reference_count"], 2)
        self.assertEqual(report["idf_exact_match_reference_count"], 1)
        self.assertEqual(report["idf_containing_data_start_reference_count"], 1)
        self.assertEqual(report["idf_legacy_unknown_provenance_reference_count"], 0)
        self.assertTrue(report["idf_reference_provenance_fully_classified"])
        self.assertFalse(report["idf_decoder_proven"])

    def test_legacy_xref_not_silently_classified_as_exact(self):
        report = correlate(*make_reports([None]), SHA)
        self.assertEqual(report["idf_exact_match_reference_count"], 0)
        self.assertEqual(report["idf_legacy_unknown_provenance_reference_count"], 1)
        self.assertFalse(report["idf_reference_provenance_fully_classified"])

    def test_legacy_provenance_fails_strict_coverage_gate(self):
        legacy = correlate(*make_reports([None]), SHA)
        exact = correlate(*make_reports(["exact_match"]), SHA)
        self.assertFalse(legacy["static_triage_coverage_adequate"])
        self.assertTrue(exact["static_triage_coverage_adequate"])
        self.assertFalse(legacy["direct_file_io_triage_candidate_with_complete_coverage"])
        self.assertFalse(legacy["open_read_idf_triage_candidate_with_complete_coverage"])

    def test_unknown_provenance_rejected(self):
        with self.assertRaisesRegex(ValueError, "provenance"):
            correlate(*make_reports(["guessed_exact"]), SHA)

if __name__ == "__main__":
    unittest.main()
