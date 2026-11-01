"""Synthetic-only tests for PE-backed Ghidra IDF function attribution.

The IDF literal and a raw PUSH pointer can be real bytes while a private
Ghidra report falsely attributes the reference to an unmapped function.
Such a function must not enter byte-corroborated graph-hop histograms.
"""
import json
import unittest

from ghidra_verified_idf_triage import analyze_verified
from test_ghidra_verified_idf_distance_tiers import with_literal


def attributed_to(function_entry):
    binary, sha, idf, api, graph = with_literal(pointer=True, boundary=True)
    hit = idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]
    hit["references_from"][0]["function_entry"] = function_entry
    return analyze_verified(binary, sha, idf, api, graph)


class ExecutableFunctionSourceTests(unittest.TestCase):
    def test_valid_executable_function_retains_evidence(self):
        report = attributed_to("00401000")
        self.assertEqual(report["verified_literal_source_function_count"], 1)
        self.assertEqual(report["verified_raw_pointer_source_function_count"], 1)
        self.assertEqual(report["verified_boundary_pointer_source_function_count"], 1)
        self.assertEqual(
            report["verified_boundary_pointer_sources_by_shortest_ghidra_file_io_hops"]["1"], 1)
        self.assertEqual(
            report["ghidra_claimed_idf_function_entries_without_executable_pe_mapping"], 0)

    def test_unmapped_function_does_not_inherit_real_literal_or_pointer(self):
        report = attributed_to("00500000")
        self.assertEqual(report["idf_literal_hits_verified_against_original_pe"], 1)
        self.assertEqual(report["idf_raw_push_or_mov_pointer_sites"], 1)
        self.assertEqual(report["verified_literal_source_function_count"], 0)
        self.assertEqual(report["verified_raw_pointer_source_function_count"], 0)
        self.assertEqual(report["verified_boundary_pointer_source_function_count"], 0)
        self.assertEqual(
            report["ghidra_claimed_idf_function_entries_without_executable_pe_mapping"], 1)
        self.assertEqual(
            report["ghidra_claimed_pointer_function_entries_without_executable_pe_mapping"], 1)
        self.assertTrue(all(value == 0 for value in
            report["verified_literal_sources_by_shortest_ghidra_file_io_hops"].values()))

    def test_pe_header_function_is_not_executable_code(self):
        report = attributed_to("00400000")
        self.assertEqual(report["verified_literal_source_function_count"], 0)
        self.assertEqual(report["verified_boundary_pointer_source_function_count"], 0)
        self.assertEqual(
            report["ghidra_claimed_idf_function_entries_without_executable_pe_mapping"], 1)
        self.assertFalse(report["idf_decoder_proven"])
        self.assertNotIn("00401080", json.dumps(report))


if __name__ == "__main__":
    unittest.main()
