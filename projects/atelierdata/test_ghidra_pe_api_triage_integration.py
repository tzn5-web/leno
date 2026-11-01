"""Synthetic-only integration: Ghidra API xrefs must not masquerade as PE-IAT calls."""
import json
import unittest

from ghidra_verified_idf_triage import analyze_verified
from test_ghidra_verified_idf_distance_tiers import with_literal


class PeIatHopSeparationTests(unittest.TestCase):
    def test_unbacked_ghidra_api_endpoint_does_not_upgrade_strict_hops(self):
        binary, sha, idf, api, graph = with_literal(pointer=True, boundary=True)
        result = analyze_verified(binary, sha, idf, api, graph)
        self.assertEqual(
            result["verified_boundary_pointer_sources_by_shortest_ghidra_file_io_hops"]["1"], 1)
        self.assertEqual(result["pe_iat_endpoint_callsites_correlated"], 0)
        self.assertEqual(result["pe_iat_direct_file_io_endpoint_function_count"], 0)
        self.assertTrue(all(value == 0 for value in
            result["verified_boundary_pointer_sources_by_shortest_pe_iat_file_io_hops"].values()))
        self.assertTrue(result["pe_iat_endpoint_byte_check_performed"])
        self.assertFalse(result["api_endpoint_calls_independently_replayed"])
        self.assertFalse(result["idf_decoder_proven"])
        self.assertNotIn("004010", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
