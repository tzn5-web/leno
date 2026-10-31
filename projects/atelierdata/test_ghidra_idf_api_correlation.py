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
