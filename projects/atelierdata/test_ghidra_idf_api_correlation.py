"""Synthetic-only tests for static Ghidra xref correlation."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from ghidra_idf_api_correlation import correlate, load_private

SHA = "a" * 64


def fixtures():
    idf = {
        "source_sha256": SHA, "executed_target_binary": False,
        "idf_decoder_proven": False,
        "keyword_hits": {
            ".rdata": {
                "MODELS.IDF:ascii": [
                    {"address": "00402000", "references_from": [
                        {"function_entry": "00401000", "source_address": "00401030"}]}],
                "ReadFile:ascii": [
                    {"address": "00403000", "references_from": [
                        {"function_entry": "00409999"}]}]
            }
        }
    }
    api = {
        "schema": "atelierdata-ghidra-file-api-xrefs-v1",
        "source_sha256": SHA, "target_executed": False,
        "idf_decoder_proven": False,
        "api_symbols": {
            "ReadFile": [{"address": "EXTERNAL:00000001", "references": [
                {"function_entry": "00401000", "instruction_mnemonic": "CALL"},
                {"function_entry": "00401100", "instruction_mnemonic": None}]}]
        }
    }
    return idf, api


class CorrelationTests(unittest.TestCase):
    def test_shared_function_is_only_a_candidate(self):
        idf, api = fixtures()
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_referencing_functions"], 1)
        self.assertEqual(result["api_referencing_functions"], 2)
        self.assertEqual(result["shared_idf_and_api_functions"], 1)
        self.assertEqual(result["shared_idf_and_api_call_or_jump_functions"], 1)
        self.assertFalse(result["idf_decoder_proven"])
        self.assertNotIn("00401000", json.dumps(result))

    def test_direct_read_family_counts_shared_call_only(self):
        idf, api = fixtures()
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_functions"], 1)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 1)
        self.assertEqual(result["shared_idf_and_api_family_functions"]["file_read"], 1)
        self.assertEqual(result["shared_idf_and_api_family_functions"]["file_open"], 0)
        self.assertEqual(result["shared_idf_and_api_family_call_or_jump_functions"]["file_read"], 1)

    def test_dynamic_lookup_only_is_not_direct_file_io(self):
        idf, api = fixtures()
        api["api_symbols"]["GetProcAddress"] = api["api_symbols"].pop("ReadFile")
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_functions"], 1)
        self.assertEqual(result["shared_idf_and_direct_file_io_functions"], 0)
        self.assertEqual(result["shared_idf_and_api_family_functions"]["dynamic_lookup"], 1)

    def test_closehandle_only_is_not_direct_file_io(self):
        idf, api = fixtures()
        api["api_symbols"]["CloseHandle"] = api["api_symbols"].pop("ReadFile")
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_functions"], 1)
        self.assertEqual(result["shared_idf_and_direct_file_io_functions"], 0)

    def test_same_function_in_multiple_io_families_is_not_double_counted(self):
        idf, api = fixtures()
        api["api_symbols"]["CreateFileW"] = copy.deepcopy(api["api_symbols"]["ReadFile"])
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_family_functions"]["file_open"], 1)
        self.assertEqual(result["shared_idf_and_api_family_functions"]["file_read"], 1)
        self.assertEqual(result["shared_idf_and_direct_file_io_functions"], 1)

    def test_data_reference_is_not_a_call_or_jump(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references"][0]["instruction_mnemonic"] = None
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_direct_file_io_functions"], 1)
        self.assertEqual(result["shared_idf_and_direct_file_io_call_or_jump_functions"], 0)

    def test_non_api_string_does_not_count_as_idf(self):
        idf, api = fixtures()
        idf["keyword_hits"][".rdata"].pop("MODELS.IDF:ascii")
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_functions"], 0)

    def test_different_executable_hash_is_rejected(self):
        idf, api = fixtures()
        api["source_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            correlate(idf, api, SHA)

    def test_claim_of_decoding_is_rejected(self):
        idf, api = fixtures()
        idf["idf_decoder_proven"] = True
        with self.assertRaisesRegex(ValueError, "decoding"):
            correlate(idf, api, SHA)

    def test_malformed_xrefs_are_rejected(self):
        idf, api = fixtures()
        idf["keyword_hits"][".rdata"]["MODELS.IDF:ascii"][0]["references_from"] = "bad"
        with self.assertRaisesRegex(ValueError, "IDF xref"):
            correlate(idf, api, SHA)

    def test_truncated_evidence_is_explicit(self):
        idf, api = fixtures()
        api["symbol_scan_truncated"] = True
        api["api_symbols"]["ReadFile"][0]["references_truncated"] = True
        result = correlate(idf, api, SHA)
        self.assertTrue(result["api_scan_or_reference_coverage_truncated"])
        self.assertEqual(result["api_symbols_with_truncated_references"], 1)
        self.assertFalse(result["idf_decoder_proven"])

    def test_invalid_truncation_flag_is_rejected(self):
        idf, api = fixtures()
        api["api_symbols"]["ReadFile"][0]["references_truncated"] = "false"
        with self.assertRaisesRegex(ValueError, "truncation"):
            correlate(idf, api, SHA)

    def test_legacy_idf_report_coverage_is_unknown(self):
        idf, api = fixtures()
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_coverage_status"], "unknown")
        self.assertTrue(result["idf_coverage_incomplete_or_unknown"])

    def test_new_idf_report_complete_coverage(self):
        idf, api = fixtures()
        idf.update(block_scan_cap_reached=False,
                   keyword_match_cap_reached=False,
                   keyword_xref_cap_reached=False,
                   short_memory_read=False,
                   keyword_scan_coverage_complete=True)
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_coverage_status"], "complete")
        self.assertFalse(result["idf_coverage_incomplete_or_unknown"])

    def test_reached_keyword_cap_marks_incomplete(self):
        idf, api = fixtures()
        idf.update(block_scan_cap_reached=False,
                   keyword_match_cap_reached=True,
                   keyword_xref_cap_reached=False,
                   short_memory_read=False,
                   keyword_scan_coverage_complete=False)
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_coverage_status"], "capped")
        self.assertTrue(result["idf_coverage_incomplete_or_unknown"])

    def test_partial_idf_coverage_metadata_rejected(self):
        idf, api = fixtures()
        idf["block_scan_cap_reached"] = False
        with self.assertRaisesRegex(ValueError, "Incomplete IDF coverage"):
            correlate(idf, api, SHA)

    def test_invalid_idf_coverage_flag_rejected(self):
        idf, api = fixtures()
        idf.update(block_scan_cap_reached=0,
                   keyword_match_cap_reached=False,
                   keyword_xref_cap_reached=False,
                   short_memory_read=False,
                   keyword_scan_coverage_complete=True)
        with self.assertRaisesRegex(ValueError, "Invalid IDF coverage"):
            correlate(idf, api, SHA)

    def test_contradictory_idf_coverage_metadata_rejected(self):
        idf, api = fixtures()
        idf.update(block_scan_cap_reached=False,
                   keyword_match_cap_reached=False,
                   keyword_xref_cap_reached=False,
                   short_memory_read=False,
                   keyword_scan_coverage_complete=False)
        with self.assertRaisesRegex(ValueError, "Contradictory IDF coverage"):
            correlate(idf, api, SHA)

    def test_report_load_rejects_symlink_when_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "private.json"
            report.write_text("{}", encoding="utf-8")
            link = root / "linked.json"
            try:
                link.symlink_to(report)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink unavailable")
            with self.assertRaisesRegex(ValueError, "linked"):
                load_private(link)


if __name__ == "__main__":
    unittest.main()
