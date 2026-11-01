"""Synthetic regression: PE-backed IDF pointer bytes cannot validate impossible Ghidra function attribution.

A source byte match is not a decoded IDF record or proof of control flow.
"""
import hashlib
import struct
import unittest

from ghidra_api_callsite_replay import replay
from ghidra_verified_idf_triage import analyze_verified
from test_ghidra_api_callsite_replay import fixtures
from test_ghidra_verified_idf_distance_tiers import with_literal


def pointer_fixture(function_entry, source_va=0x401030, second_section_executable=False):
    data, _, idf, api = fixtures()
    modified = bytearray(data)
    if second_section_executable:
        # The synthetic .idata section is now also executable, but it is
        # still a DIFFERENT section from the reported function entry.
        second = 0x98 + 224 + 40
        struct.pack_into("<I", modified, second + 36, 0x60000020)
    raw = (0x200 + source_va - 0x401000 if source_va < 0x402000
           else 0x400 + source_va - 0x402000)
    modified[raw:raw + 5] = b"\x68" + struct.pack("<I", 0x402100)
    data = bytes(modified)
    sha = hashlib.sha256(data).hexdigest()
    md5 = hashlib.md5(data).hexdigest()
    for report in (idf, api):
        report["source_sha256"] = sha
        report["source_md5"] = md5
    ref = idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"][0]
    ref.update({
        "function_entry": function_entry,
        "source_address": "RAM:%08X" % source_va,
        "reference_type": "DATA",
        "reference_is_data": True,
        "instruction_start_address": "RAM:%08X" % source_va,
        "instruction_length": 5,
        "instruction_mnemonic": "PUSH",
    })
    return data, sha, idf, api


class PointerFunctionOwnershipTests(unittest.TestCase):
    def test_valid_same_section_preceding_function_retains_correlation(self):
        data, sha, idf, api = pointer_fixture("00401000")
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_xrefs_with_raw_push_or_mov_literal_va"], 1)
        self.assertEqual(result["idf_xrefs_with_ghidra_boundary_and_raw_pointer"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_raw_pointer_functions"], 1)
        self.assertEqual(result["matching_api_sites_in_ghidra_idf_pointer_functions"], 1)
        self.assertFalse(result["idf_decoder_proven"])

    def test_function_entry_after_pointer_site_is_not_its_owner(self):
        data, sha, idf, api = pointer_fixture("00401040")
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_xrefs_with_raw_push_or_mov_literal_va"], 1)
        self.assertEqual(result["idf_xrefs_with_ghidra_boundary_and_raw_pointer"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_raw_pointer_functions"], 0)
        self.assertEqual(result["matching_api_sites_in_ghidra_idf_pointer_functions"], 0)
        self.assertEqual(result["ghidra_claimed_idf_pointer_functions_rejected_by_pe_ownership"], 1)

    def test_separate_executable_sections_do_not_establish_ownership(self):
        data, sha, idf, api = pointer_fixture(
            "00401000", source_va=0x402130, second_section_executable=True)
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_xrefs_with_raw_push_or_mov_literal_va"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_raw_pointer_functions"], 0)
        self.assertEqual(result["matching_api_sites_in_ghidra_idf_pointer_functions"], 0)

    def test_verified_callgraph_pointer_tier_excludes_future_function(self):
        binary, sha, idf, api, graph = with_literal(pointer=True, boundary=True)
        idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"][0][
            "function_entry"] = "004010A0"
        report = analyze_verified(binary, sha, idf, api, graph)
        self.assertEqual(report["idf_raw_push_or_mov_pointer_sites"], 1)
        self.assertEqual(report["idf_raw_pointer_sites_with_ghidra_boundary_metadata"], 1)
        self.assertEqual(report["verified_raw_pointer_source_function_count"], 0)
        self.assertEqual(report["verified_boundary_pointer_source_function_count"], 0)
        self.assertEqual(
            report["ghidra_claimed_pointer_function_entries_with_impossible_source_ownership"], 1)
        self.assertFalse(report["runtime_reachability_proven"])


if __name__ == "__main__":
    unittest.main()
