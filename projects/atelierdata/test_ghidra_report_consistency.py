"""Synthetic-only tests for Ghidra report consistency; no original binaries."""
import copy
import json
import unittest
from ghidra_report_consistency import validate


def fixture():
    triage = {
        "schema": "atelierdata-loadlibrary-literal-private-v1",
        "sha256": "a" * 64, "md5": "b" * 32,
        "candidates": [
            {"call_va": 4096, "literal": "synthetic.dll", "iat_va": 8192},
            {"call_va": 4107, "literal": None, "iat_va": 8192},
        ],
    }
    ghidra = {
        "schema": "atelierdata-ghidra-loadlibrary-private-v1",
        "source_sha256": "a" * 64, "ghidra_executable_md5_verified": True,
        "target_executed": False, "cfg_reachability_proven": False,
        "idf_decoder_proven": False, "candidate_count": 2,
        "recognized_instruction_pairs": 1, "verified_literal_pointers": 1,
        "iat_references": 1, "verified_candidates_in_direct_call_graph": 1,
        "ghidra_declared_entry_roots_with_functions": 1,
        "direct_call_graph_functions_visited": 3,
        "direct_call_graph_complete_within_budget": True,
        "candidates": [
            {"call_va": 4096, "push_call_instruction_verified": True,
             "literal_pointer_verified": True, "ghidra_reference_to_iat": True,
             "in_ghidra_entrypoint_direct_call_graph": True,
             "containing_function": "private_function_name"},
            {"call_va": 4107, "push_call_instruction_verified": False,
             "literal_pointer_verified": False, "ghidra_reference_to_iat": False,
             "in_ghidra_entrypoint_direct_call_graph": False,
             "containing_function": None},
        ],
    }
    return triage, ghidra


class GhidraConsistencyTests(unittest.TestCase):
    def test_valid_aggregate_excludes_private_addresses_and_names(self):
        triage, ghidra = fixture()
        summary = validate(triage, ghidra)
        self.assertEqual(summary["recognized_instruction_pairs"], 1)
        self.assertFalse(summary["idf_decoder_proven"])
        output = json.dumps(summary)
        self.assertNotIn("private_function_name", output)
        self.assertNotIn("synthetic.dll", output)
        self.assertNotIn("4096", output)

    def test_sha_mismatch_rejected(self):
        triage, ghidra = fixture()
        ghidra["source_sha256"] = "c" * 64
        with self.assertRaises(ValueError):
            validate(triage, ghidra)

    def test_aggregate_tampering_rejected(self):
        triage, ghidra = fixture()
        ghidra["verified_literal_pointers"] = 2
        with self.assertRaises(ValueError):
            validate(triage, ghidra)

    def test_duplicate_address_rejected(self):
        triage, ghidra = fixture()
        ghidra["candidates"][1]["call_va"] = 4096
        with self.assertRaises(ValueError):
            validate(triage, ghidra)

    def test_literal_without_instruction_rejected(self):
        triage, ghidra = fixture()
        ghidra["candidates"][0]["push_call_instruction_verified"] = False
        with self.assertRaises(ValueError):
            validate(triage, ghidra)

    def test_claim_of_decoder_proof_rejected(self):
        triage, ghidra = fixture()
        ghidra["idf_decoder_proven"] = True
        with self.assertRaises(ValueError):
            validate(triage, ghidra)

    def test_unverified_ghidra_identity_rejected(self):
        triage, ghidra = fixture()
        ghidra["ghidra_executable_md5_verified"] = False
        with self.assertRaises(ValueError):
            validate(triage, ghidra)

    def test_graph_claim_without_function_rejected(self):
        triage, ghidra = fixture()
        ghidra["candidates"][0]["containing_function"] = None
        with self.assertRaises(ValueError):
            validate(triage, ghidra)

    def test_wrong_schema_rejected(self):
        triage, ghidra = fixture()
        ghidra["schema"] = "other"
        with self.assertRaises(ValueError):
            validate(triage, ghidra)


if __name__ == "__main__":
    unittest.main()
