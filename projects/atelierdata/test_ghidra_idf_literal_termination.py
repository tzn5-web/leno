"""Synthetic regression: a .IDF substring is not a verified complete literal.

The private source PE is never needed by these tests.
"""
import hashlib
import struct
import unittest

from ghidra_api_callsite_replay import replay
from ghidra_verified_idf_triage import analyze_verified
from test_ghidra_verified_idf_distance_tiers import with_literal
from test_ghidra_api_callsite_replay import fixtures


def rebind(binary, idf, api):
    data = bytes(binary)
    sha = hashlib.sha256(data).hexdigest()
    md5 = hashlib.md5(data).hexdigest()
    for report in (idf, api):
        report["source_sha256"] = sha
        report["source_md5"] = md5
    return data, sha


class IDFLiteralTerminationTests(unittest.TestCase):
    def test_ascii_idf_extension_prefix_is_not_complete_filename(self):
        data, _, idf, api = fixtures()
        changed = bytearray(data)
        changed[0x50a:0x50b] = b"X"  # MODELS.IDFX, not MODELS.IDF
        data, sha = rebind(changed, idf, api)
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_literal_hits_without_file_backed_nul_terminator"], 1)
        self.assertEqual(result["idf_literal_hits_verified_against_source_pe"], 0)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 0)
        self.assertEqual(result["raw_indirect_import_sites_with_matching_api_name"], 1)
        self.assertFalse(result["idf_decoder_proven"])

    def test_utf16_idf_extension_prefix_is_not_complete_filename(self):
        data, _, idf, api = fixtures()
        changed = bytearray(data)
        changed[0x500:0x514] = "MODELS.IDF".encode("utf-16le")
        changed[0x514:0x516] = "X".encode("utf-16le")
        hits = idf["keyword_hits"][".rdata"]
        hits["MODELS.IDF:utf16le"] = hits.pop("MODELS.IDF:ascii")
        data, sha = rebind(changed, idf, api)
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_literal_hits_without_file_backed_nul_terminator"], 1)
        self.assertEqual(result["idf_literal_hits_verified_against_source_pe"], 0)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 0)

    def test_terminator_must_be_file_backed_not_only_virtual(self):
        data, _, idf, api = fixtures()
        changed = bytearray(data)
        # .idata RVA 0x2000, literal RVA 0x2100, ten-byte name:
        # the NUL at RVA 0x210a is outside the initialized section.
        idata_section = 0x98 + 224 + 40
        struct.pack_into("<I", changed, idata_section + 8, 0x10a)
        data, sha = rebind(changed, idf, api)
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_literal_hits_without_file_backed_nul_terminator"], 1)
        self.assertEqual(result["idf_literal_hits_verified_against_source_pe"], 0)

    def test_unterminated_literal_cannot_enter_verified_callgraph_tier(self):
        data, _, idf, api, graph = with_literal(pointer=True, boundary=True)
        changed = bytearray(data)
        changed[0x28a] = ord("X")
        data = bytes(changed)
        sha = hashlib.sha256(data).hexdigest()
        md5 = hashlib.md5(data).hexdigest()
        for report in (idf, api, graph):
            report["source_sha256"] = sha
            report["source_md5"] = md5
        result = analyze_verified(data, sha, idf, api, graph)
        self.assertEqual(result["idf_literal_hits_without_file_backed_nul_terminator"], 1)
        self.assertEqual(result["verified_literal_source_function_count"], 0)
        self.assertEqual(result["verified_raw_pointer_source_function_count"], 0)
        self.assertEqual(result["verified_boundary_pointer_source_function_count"], 0)
        self.assertFalse(result["idf_decoder_proven"])

    def test_exact_terminated_ascii_literal_remains_valid(self):
        data, sha, idf, api = fixtures()
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_literal_hits_without_file_backed_nul_terminator"], 0)
        self.assertEqual(result["idf_literal_hits_verified_against_source_pe"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 1)

    def test_exact_terminated_utf16_literal_remains_valid(self):
        data, _, idf, api = fixtures()
        changed = bytearray(data)
        changed[0x500:0x514] = "MODELS.IDF".encode("utf-16le")
        hits = idf["keyword_hits"][".rdata"]
        hits["MODELS.IDF:utf16le"] = hits.pop("MODELS.IDF:ascii")
        data, sha = rebind(changed, idf, api)
        result = replay(data, sha, idf, api)
        self.assertEqual(result["idf_literal_hits_without_file_backed_nul_terminator"], 0)
        self.assertEqual(result["idf_literal_hits_verified_against_source_pe"], 1)
        self.assertEqual(result["matching_api_sites_in_idf_string_referencing_functions"], 1)


if __name__ == "__main__":
    unittest.main()
