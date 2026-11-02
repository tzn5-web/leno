"""Synthetic regression: incomplete Ghidra IDF pointer claims fail closed.

Raw PE pointer bytes may be counted, but they cannot establish ownership
or a Ghidra instruction boundary when any sibling xref is incomplete.
No original executable or proprietary IDF file is used.
"""
import copy
import unittest

from ghidra_api_callsite_replay import replay
from ghidra_verified_idf_triage import analyze_verified
from test_ghidra_idf_pointer_ownership import pointer_fixture
from test_ghidra_verified_idf_distance_tiers import with_literal


def _refs(report):
    return report["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"]


class IncompletePointerClaimTests(unittest.TestCase):
    def test_missing_owner_taints_valid_sibling_at_same_raw_site(self):
        data, sha, idf, api = pointer_fixture("00401000")
        orphan = copy.deepcopy(_refs(idf)[0])
        orphan.pop("function_entry")
        _refs(idf).append(orphan)
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_xrefs_with_raw_push_or_mov_literal_va"], 1)
        self.assertEqual(result["idf_raw_pointer_sites_with_conflicting_ghidra_claims"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_raw_pointer_functions"], 0)
        self.assertEqual(result["idf_xrefs_with_ghidra_boundary_and_raw_pointer"], 0)
        self.assertFalse(result["idf_decoder_proven"])

    def test_only_missing_owner_is_not_accepted_or_crashing(self):
        data, sha, idf, api = pointer_fixture("00401000")
        _refs(idf)[0].pop("function_entry")
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_xrefs_with_raw_push_or_mov_literal_va"], 1)
        self.assertEqual(result["idf_raw_pointer_sites_with_conflicting_ghidra_claims"], 1)
        self.assertEqual(result["ghidra_claimed_idf_pointer_function_count"], 0)
        self.assertEqual(result["matching_api_sites_in_idf_raw_pointer_functions"], 0)

    def test_flow_type_with_data_boolean_cannot_validate_boundary(self):
        data, sha, idf, api = pointer_fixture("00401000")
        _refs(idf)[0]["reference_type"] = "UNCONDITIONAL_CALL"
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_xrefs_with_raw_push_or_mov_literal_va"], 1)
        self.assertEqual(result["idf_xrefs_with_ghidra_boundary_and_raw_pointer"], 0)
        self.assertEqual(result["matching_api_sites_in_idf_raw_pointer_functions"], 1)
        self.assertEqual(result["matching_api_sites_in_ghidra_idf_pointer_functions"], 0)

    def test_verified_graph_rejects_incomplete_owner_sibling(self):
        binary, sha, idf, api, graph = with_literal(pointer=True, boundary=True)
        orphan = copy.deepcopy(_refs(idf)[0])
        orphan["function_entry"] = None
        _refs(idf).append(orphan)
        result = analyze_verified(binary, sha, idf, api, graph)
        self.assertEqual(result["idf_pointer_sites_with_conflicting_ghidra_claims"], 1)
        self.assertEqual(result["verified_raw_pointer_source_function_count"], 0)
        self.assertEqual(result["verified_boundary_pointer_source_function_count"], 0)
        self.assertFalse(result["idf_decoder_proven"])


if __name__ == "__main__":
    unittest.main()
