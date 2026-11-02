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
    b[0x500:0x50a] = b"MODELS.IDF"  # Synthetic string at PE VA 0x402100
    b[0x220:0x226] = b"\xff\x15" + struct.pack("<I", 0x4020c0)
    return bytes(b)


def fixtures():
    data = synthetic_pe()
    sha = hashlib.sha256(data).hexdigest()
    idf = {
        "source_sha256": sha, "source_md5": hashlib.md5(data).hexdigest(),
        "executed_target_binary": False,
        "idf_decoder_proven": False, "ghidra_import_sha256_verified": True,
        "keyword_hits": {".rdata": {"MODELS.IDF:ascii": [{
            "address": "RAM:00402100",
            "references_from": [{"function_entry": "00401000"}]}]}}
    }
    api = {
        "schema": "atelierdata-ghidra-file-api-xrefs-v1",
        "source_sha256": sha, "source_md5": hashlib.md5(data).hexdigest(),
        "target_executed": False,
        "idf_decoder_proven": False, "ghidra_program_sha256_verified": True,
        "ghidra_program_md5_verified": True,
        "api_symbols": {"ReadFile": [{"references": [{
            "source_address": "RAM:00401020", "function_entry": "0x401000",
            "reference_type": "UNCONDITIONAL_CALL",
            "instruction_start_address": "RAM:00401020",
            "instruction_length": 6,
            "instruction_mnemonic": "CALL",
            "reference_is_call_or_jump": True}]}]}
    }
    return data, sha, idf, api


class ReplayTests(unittest.TestCase):
    def test_matching_indirect_callsite_and_shared_idf_function(self):
        data, sha, idf, api = fixtures()
        result = replay(data, sha, idf, api)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 1)
        self.assertEqual(result["idf_literal_hits_verified_against_source_pe"], 1)
        self.assertFalse(result["idf_decoder_proven"])
        self.assertNotIn("004010", json.dumps(result))
        self.assertNotIn("ReadFile", json.dumps(result))


    def test_raw_push_immediate_to_idf_literal_is_independent_narrow_evidence(self):
        data, sha, idf, api = fixtures()
        modified = bytearray(data)
        modified[0x230:0x235] = bytes((0x68,)) + struct.pack("<I", 0x402100)
        modified = bytes(modified)
        new_sha = hashlib.sha256(modified).hexdigest()
        for report in (idf, api):
            report["source_sha256"] = new_sha
            report["source_md5"] = hashlib.md5(modified).hexdigest()
        ref = idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"][0]
        ref["source_address"] = "RAM:00401030"
        result = replay(modified, new_sha, idf, api)
        self.assertEqual(result["idf_xrefs_with_raw_push_or_mov_literal_va"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_raw_pointer_functions"], 1)
        self.assertFalse(result["instruction_boundaries_independently_verified"])
        self.assertNotIn("00401030", json.dumps(result))
        # Duplicated Ghidra rows must not inflate physical pointer evidence.
        idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"].append(copy.deepcopy(ref))
        repeated = replay(modified, new_sha, idf, api)
        self.assertEqual(repeated["idf_xrefs_with_raw_push_or_mov_literal_va"], 1)

    def test_ghidra_idf_data_xref_instruction_boundary_tier(self):
        data, sha, idf, api = fixtures()
        modified = bytearray(data)
        modified[0x230:0x235] = bytes((0x68,)) + struct.pack("<I", 0x402100)
        modified = bytes(modified)
        sha = hashlib.sha256(modified).hexdigest()
        for report in (idf, api):
            report["source_sha256"] = sha
            report["source_md5"] = hashlib.md5(modified).hexdigest()
        ref = idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"][0]
        ref.update(source_address="RAM:00401030",
                   reference_type="DATA", reference_is_data=True,
                   instruction_start_address="RAM:00401030",
                   instruction_length=5, instruction_mnemonic="PUSH")
        result = replay(modified, sha, idf, api)
        self.assertEqual(result["idf_xrefs_with_raw_push_or_mov_literal_va"], 1)
        self.assertEqual(result["idf_xrefs_with_ghidra_boundary_and_raw_pointer"], 1)
        self.assertEqual(result["matching_api_sites_in_ghidra_idf_pointer_functions"], 1)
        self.assertFalse(result["instruction_boundaries_independently_verified"])
        self.assertNotIn("00401030", json.dumps(result))
        ref_copy = copy.deepcopy(ref)
        for key, wrong in (
                ("reference_is_data", False),
                ("instruction_start_address", "RAM:00401031"),
                ("instruction_length", 6),
                ("instruction_mnemonic", "MOV"),
                ("instruction_start_address", None)):
            with self.subTest(field=key, invalid=wrong):
                ref.update(ref_copy)
                ref[key] = wrong
                invalid = replay(modified, sha, idf, api)
                self.assertEqual(invalid["idf_xrefs_with_raw_push_or_mov_literal_va"], 1)
                self.assertEqual(invalid["idf_xrefs_with_ghidra_boundary_and_raw_pointer"], 0)
                self.assertEqual(invalid["matching_api_sites_in_ghidra_idf_pointer_functions"], 0)

    def test_ghidra_idf_mov_immediate_boundary_tier(self):
        data, sha, idf, api = fixtures()
        modified = bytearray(data)
        modified[0x230:0x235] = bytes((0xb8,)) + struct.pack("<I", 0x402100)
        modified = bytes(modified)
        sha = hashlib.sha256(modified).hexdigest()
        for report in (idf, api):
            report["source_sha256"] = sha
            report["source_md5"] = hashlib.md5(modified).hexdigest()
        ref = idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"][0]
        ref.update(source_address="RAM:00401030",
                   reference_type="DATA", reference_is_data=True,
                   instruction_start_address="RAM:00401030",
                   instruction_length=5, instruction_mnemonic="MOV")
        self.assertEqual(replay(modified, sha, idf, api)[
            "idf_xrefs_with_ghidra_boundary_and_raw_pointer"], 1)
        ref["instruction_mnemonic"] = "PUSH"
        self.assertEqual(replay(modified, sha, idf, api)[
            "idf_xrefs_with_ghidra_boundary_and_raw_pointer"], 0)

    def test_raw_idf_pointer_evidence_rejects_wrong_operand_and_data_source(self):
        data, sha, idf, api = fixtures()
        ref = idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"][0]
        ref["source_address"] = "RAM:00401030"
        # A reported xref without the matching raw immediate is not evidence.
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_xrefs_with_raw_push_or_mov_literal_va"], 0)
        self.assertEqual(result["matching_api_sites_in_idf_raw_pointer_functions"], 0)
        # A non-executable section cannot be counted as an instruction site.
        ref["source_address"] = "RAM:00402100"
        self.assertEqual(replay(data, sha, idf, api)["idf_xrefs_with_raw_push_or_mov_literal_va"], 0)
        # The older Ghidra-reported shared-function count is kept separate.
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 1)

    def test_missing_idf_literal_address_is_not_independent_evidence(self):
        data, sha, idf, api = fixtures()
        hit = idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]
        hit.pop("address")
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_literal_hits_missing_address"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 0)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 1)

    def test_mismatched_literal_bytes_are_not_shared_idf_evidence(self):
        data, sha, idf, api = fixtures()
        hit = idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]
        hit["address"] = "RAM:00402110"  # Mapped but not the IDF string.
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_literal_hits_unmapped_or_mismatched"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 0)

    def test_unmapped_literal_is_not_shared_idf_evidence(self):
        data, sha, idf, api = fixtures()
        hit = idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]
        hit["address"] = "RAM:90000000"
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_literal_hits_unmapped_or_mismatched"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 0)

    def test_utf16_literal_is_checked_at_reported_address(self):
        data, sha, idf, api = fixtures()
        modified = bytearray(data)
        modified[0x500:0x514] = "MODELS.IDF".encode("utf-16le")
        modified = bytes(modified)
        new_sha = hashlib.sha256(modified).hexdigest()
        for report in (idf, api):
            report["source_sha256"] = new_sha
            report["source_md5"] = hashlib.md5(modified).hexdigest()
        hits = idf["keyword_hits"][".rdata"]
        hits["MODELS.IDF:utf16le"] = hits.pop("MODELS.IDF:ascii")
        result = replay(modified, new_sha, idf, api)
        self.assertEqual(result["idf_literal_hits_verified_against_source_pe"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 1)

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

    def test_legacy_flow_reference_without_instruction_evidence_is_excluded(self):
        data, sha, idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref.pop("instruction_start_address")
        result = replay(data, sha, idf, api)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)
        self.assertEqual(result["references_missing_ghidra_instruction_boundary_evidence"], 1)

    def test_reference_from_middle_of_instruction_is_excluded(self):
        data, sha, idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref["instruction_start_address"] = "RAM:0040101f"
        result = replay(data, sha, idf, api)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)
        self.assertEqual(result["references_with_inconsistent_ghidra_instruction_boundary_evidence"], 1)

    def test_non_six_byte_or_wrong_mnemonic_is_excluded(self):
        data, sha, idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref["instruction_length"] = 5
        self.assertEqual(replay(data, sha, idf, api)["references_with_inconsistent_ghidra_instruction_boundary_evidence"], 1)
        ref["instruction_length"] = 6
        ref["instruction_mnemonic"] = "JMP"
        self.assertEqual(replay(data, sha, idf, api)["references_with_inconsistent_ghidra_instruction_boundary_evidence"], 1)

    def test_missing_explicit_flow_boolean_is_not_assumed_true(self):
        data, sha, idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref.pop("reference_is_call_or_jump")
        self.assertEqual(replay(data, sha, idf, api)["raw_indirect_import_sites_with_matching_api_name"], 0)

    def test_conditional_flow_type_is_not_indirect_ff15_evidence(self):
        data, sha, idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        ref["reference_type"] = "CONDITIONAL_CALL"
        self.assertEqual(replay(data, sha, idf, api)["raw_indirect_import_sites_with_matching_api_name"], 0)

    def test_raw_import_name_mismatch_is_not_corroborated(self):
        data, sha, idf, api = fixtures()
        api["api_symbols"]["CreateFileA"] = api["api_symbols"].pop("ReadFile")
        self.assertEqual(replay(data, sha, idf, api)["raw_indirect_import_sites_with_matching_api_name"], 0)

    def test_unmapped_source_is_not_corroborated(self):
        data, sha, idf, api = fixtures()
        ref = api["api_symbols"]["ReadFile"][0]["references"][0]
        # Preserve internally consistent Ghidra instruction evidence so this
        # test reaches the raw PE mapping check rather than boundary rejection.
        ref["source_address"] = "0x90000000"
        ref["instruction_start_address"] = "0x90000000"
        result = replay(data, sha, idf, api)
        self.assertEqual(result["sites_without_unique_raw_mapping"], 1)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)

    def test_opcode_flow_type_conflict_is_not_evidence(self):
        data, sha, idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"][0]["reference_type"] = "UNCONDITIONAL_JUMP"
        api["api_symbols"]["ReadFile"][0]["references"][0]["instruction_mnemonic"] = "JMP"
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

    def test_conflicting_containing_functions_do_not_inflate_callsites(self):
        data, sha, idf, api = fixtures()
        refs = api["api_symbols"]["ReadFile"][0]["references"]
        other = copy.deepcopy(refs[0])
        other["function_entry"] = "00401100"
        refs.append(other)
        result = replay(data, sha, idf, api)
        self.assertEqual(result["reported_api_flow_sites_with_address_inspected"], 1)
        self.assertEqual(result["unique_sites_repeated_in_report"], 1)
        self.assertEqual(result["sites_with_conflicting_reported_attribution"], 1)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)
        refs.reverse()
        self.assertEqual(replay(data, sha, idf, api), result)

    def test_conflicting_api_names_at_one_physical_site_are_excluded(self):
        data, sha, idf, api = fixtures()
        # One instruction cannot independently corroborate two reported API
        # targets. Both names share the exact same physical source address.
        api["api_symbols"]["CreateFileA"] = copy.deepcopy(api["api_symbols"]["ReadFile"])
        result = replay(data, sha, idf, api)
        self.assertEqual(result["reported_api_flow_sites_with_address_inspected"], 1)
        self.assertEqual(result["unique_sites_repeated_in_report"], 1)
        self.assertEqual(result["sites_with_conflicting_reported_attribution"], 1)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 0)
        reversed_symbols = dict(reversed(list(api["api_symbols"].items())))
        api["api_symbols"] = reversed_symbols
        self.assertEqual(replay(data, sha, idf, api), result)

    def test_conflicting_call_and_jump_reports_are_excluded(self):
        data, sha, idf, api = fixtures()
        refs = api["api_symbols"]["ReadFile"][0]["references"]
        other = copy.deepcopy(refs[0])
        other["reference_type"] = "UNCONDITIONAL_JUMP"
        other["instruction_mnemonic"] = "JMP"
        refs.append(other)
        result = replay(data, sha, idf, api)
        self.assertEqual(result["sites_with_conflicting_reported_attribution"], 1)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)

    def test_raw_section_padding_is_not_mapped_as_code(self):
        data, sha, idf, api = fixtures()
        modified = bytearray(data)
        # .text VirtualSize is 0x20; reported site is at RVA 0x1020.
        struct.pack_into("<I", modified, 0x98 + 224 + 8, 0x20)
        modified = bytes(modified)
        new_sha = hashlib.sha256(modified).hexdigest()
        for report in (idf, api):
            report["source_sha256"] = new_sha
            report["source_md5"] = hashlib.md5(modified).hexdigest()
        result = replay(modified, new_sha, idf, api)
        self.assertEqual(result["sites_without_unique_raw_mapping"], 1)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)

    def test_private_reports_are_bound_to_original_md5(self):
        data, sha, idf, api = fixtures()
        for report in (idf, api):
            saved = report["source_md5"]
            report["source_md5"] = "0" * 32
            with self.assertRaisesRegex(ValueError, "source MD5 mismatch"):
                replay(data, sha, idf, api)
            report["source_md5"] = saved

    def test_duplicate_sites_not_double_counted_and_reports_immutable(self):
        data, sha, idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"] *= 2
        before = copy.deepcopy(api)
        result = replay(data, sha, idf, api)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 1)
        self.assertEqual(result["unique_sites_repeated_in_report"], 1)
        self.assertEqual(api, before)


    def test_api_caller_after_callsite_is_not_corroborated(self):
        data, sha, idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"][0]["function_entry"] = "00401030"
        result = replay(data, sha, idf, api)
        self.assertEqual(result["api_callsites_with_impossible_function_ownership"], 1)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 0)

    def test_api_caller_in_nonexecuting_section_is_not_corroborated(self):
        data, sha, idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"][0]["function_entry"] = "00402000"
        result = replay(data, sha, idf, api)
        self.assertEqual(result["api_callsites_with_impossible_function_ownership"], 1)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)

    def test_malformed_duplicate_cannot_upgrade_valid_api_site(self):
        data, sha, idf, api = fixtures()
        refs = api["api_symbols"]["ReadFile"][0]["references"]
        good = copy.deepcopy(refs[0])
        for field, value in (
                ("instruction_length", 5),
                ("instruction_start_address", "RAM:00401021"),
                ("function_entry", None),
                ("reference_is_call_or_jump", None)):
            with self.subTest(field=field):
                bad = copy.deepcopy(good)
                bad[field] = value
                refs[:] = [good, bad]
                result = replay(data, sha, idf, api)
                self.assertEqual(result["sites_with_conflicting_reported_attribution"], 1)
                self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 0)
                refs.reverse()
                self.assertEqual(replay(data, sha, idf, api), result)
        refs[:] = [good]
        self.assertEqual(replay(data, sha, idf, api)[
            "raw_indirect_import_sites_with_matching_api_name"], 1)


if __name__ == "__main__":
    unittest.main()
