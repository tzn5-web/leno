"""Synthetic-only tests for read-only Ghidra API callsite replay."""
import copy
import hashlib
import json
import struct
import unittest

from ghidra_api_callsite_replay import replay


def synthetic_pe():
    b = bytearray(1536)
    b[:2] = b"MZ"
    struct.pack_into("<I", b, 0x3c, 0x80)
    b[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", b, 0x84, 0x14c, 2, 0, 0, 0, 224, 0x0102)
    opt = 0x98
    struct.pack_into("<H", b, opt, 0x10b)
    struct.pack_into("<I", b, opt + 28, 0x400000)
    struct.pack_into("<I", b, opt + 60, 0x200)
    struct.pack_into("<I", b, opt + 92, 16)
    struct.pack_into("<II", b, opt + 104, 0x2020, 40)
    sec = opt + 224
    b[sec:sec + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", b, sec + 8, 0x200, 0x1000, 0x200, 0x200)
    struct.pack_into("<I", b, sec + 36, 0x60000020)
    sec += 40
    b[sec:sec + 8] = b".idata\0\0"
    struct.pack_into("<IIII", b, sec + 8, 0x200, 0x2000, 0x200, 0x400)
    struct.pack_into("<I", b, sec + 36, 0x40000040)
    struct.pack_into("<IIIII", b, 0x420, 0x20a0, 0, 0, 0x2080, 0x20c0)
    b[0x480:0x48d] = b"KERNEL32.dll\0"
    struct.pack_into("<II", b, 0x4a0, 0x20e0, 0)
    struct.pack_into("<II", b, 0x4c0, 0x20e0, 0)
    b[0x4e2:0x4eb] = b"ReadFile\0"
    b[0x220:0x226] = b"\xff\x15" + struct.pack("<I", 0x4020c0)
    return bytes(b)


def fixtures():
    data = synthetic_pe()
    sha = hashlib.sha256(data).hexdigest()
    idf = {
        "source_sha256": sha, "executed_target_binary": False,
        "idf_decoder_proven": False, "ghidra_import_sha256_verified": True,
        "keyword_hits": {".rdata": {"MODELS.IDF:ascii": [{
            "references_from": [{"function_entry": "00401000"}]}]}}
    }
    api = {
        "schema": "atelierdata-ghidra-file-api-xrefs-v1",
        "source_sha256": sha, "target_executed": False,
        "idf_decoder_proven": False, "ghidra_program_sha256_verified": True,
        "ghidra_program_md5_verified": True,
        "api_symbols": {"ReadFile": [{"references": [{
            "source_address": "RAM:00401020", "function_entry": "0x401000",
            "reference_type": "UNCONDITIONAL_CALL",
            "reference_is_call_or_jump": True}]}]}
    }
    return data, sha, idf, api


class ReplayTests(unittest.TestCase):
    def test_matching_indirect_callsite_and_shared_idf_function(self):
        data, sha, idf, api = fixtures()
        result = replay(data, sha, idf, api)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 1)
        self.assertFalse(result["idf_decoder_proven"])
        self.assertNotIn("004010", json.dumps(result))
        self.assertNotIn("ReadFile", json.dumps(result))

    def test_different_idf_function_does_not_match(self):
        data, sha, idf, api = fixtures()
        idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"][0]["function_entry"] = "00401100"
        result = replay(data, sha, idf, api)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 0)

    def test_data_reference_and_mnemonic_only_do_not_count(self):
        data, sha, idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref["reference_type"] = "DATA"
        ref["reference_is_call_or_jump"] = False
        ref["instruction_mnemonic"] = "CALL"
        self.assertEqual(replay(data, sha, idf, api)["reported_api_flow_sites_with_address_inspected"], 0)
        ref.pop("reference_type")
        ref.pop("reference_is_call_or_jump")
        self.assertEqual(replay(data, sha, idf, api)["reported_api_flow_sites_with_address_inspected"], 0)

    def test_raw_import_name_mismatch_is_not_corroborated(self):
        data, sha, idf, api = fixtures()
        api["api_symbols"]["CreateFileA"] = api["api_symbols"].pop("ReadFile")
        self.assertEqual(replay(data, sha, idf, api)["raw_indirect_import_sites_with_matching_api_name"], 0)

    def test_unmapped_source_is_not_corroborated(self):
        data, sha, idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"][0]["source_address"] = "0x90000000"
        result = replay(data, sha, idf, api)
        self.assertEqual(result["sites_without_unique_raw_mapping"], 1)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)

    def test_opcode_flow_type_conflict_is_not_evidence(self):
        data, sha, idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"][0]["reference_type"] = "UNCONDITIONAL_JUMP"
        result = replay(data, sha, idf, api)
        self.assertEqual(result["opcode_vs_ghidra_flow_type_conflicts"], 1)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)

    def test_sha256_and_claimed_identity_required(self):
        data, sha, idf, api = fixtures()
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            replay(data, "0" * 64, idf, api)
        api["ghidra_program_md5_verified"] = False
        with self.assertRaisesRegex(ValueError, "identity flags"):
            replay(data, sha, idf, api)

    def test_duplicate_sites_not_double_counted_and_reports_immutable(self):
        data, sha, idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"] *= 2
        before = copy.deepcopy(api)
        result = replay(data, sha, idf, api)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 1)
        self.assertEqual(result["unique_sites_repeated_in_report"], 1)
        self.assertEqual(api, before)


if __name__ == "__main__":
    unittest.main()
