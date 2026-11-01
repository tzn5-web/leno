"""Synthetic-only regression tests for Ghidra function address correlation.

No proprietary PE, IDF or private report is needed.
"""
import copy
import unittest

from ghidra_idf_api_correlation import correlate

SHA = "a" * 64


def fixtures(idf_address="00401000", api_address="00401000"):
    idf = {
        "source_sha256": SHA, "executed_target_binary": False,
        "idf_decoder_proven": False,
        "keyword_hits": {".rdata": {
            "MODELS.IDF:ascii": [{"references_from": [
                {"function_entry": idf_address}]}]
        }},
    }
    api = {
        "schema": "atelierdata-ghidra-file-api-xrefs-v1",
        "source_sha256": SHA, "target_executed": False,
        "idf_decoder_proven": False,
        "api_symbols": {"ReadFile": [{
            "references": [{"function_entry": api_address,
                            "instruction_mnemonic": "CALL",
                            "reference_type": "UNCONDITIONAL_CALL"}]
        }]},
    }
    return idf, api


class AddressNormalizationTests(unittest.TestCase):
    def test_leading_zero_prefix_and_case_match(self):
        idf, api = fixtures("00401000", "RAM:0x401000")
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_functions"], 1)
        self.assertEqual(result["shared_idf_and_api_call_or_jump_functions"], 1)
        self.assertNotIn("401000", str(result))

    def test_different_address_spaces_do_not_collide(self):
        idf, api = fixtures("RAM:00401000", "EXTERNAL:00401000")
        result = correlate(idf, api, SHA)
        self.assertEqual(result["shared_idf_and_api_functions"], 0)

    def test_distinct_ram_addresses_do_not_collide(self):
        idf, api = fixtures("00401000", "00401001")
        self.assertEqual(correlate(idf, api, SHA)["shared_idf_and_api_functions"], 0)

    def test_invalid_idf_address_rejected(self):
        for invalid in ("00401000:garbage", "-1", "ram:0x", "0xGG", " "):
            with self.subTest(invalid=invalid):
                idf, api = fixtures(invalid, "00401000")
                with self.assertRaisesRegex(ValueError, "function address"):
                    correlate(idf, api, SHA)

    def test_invalid_api_address_rejected(self):
        idf, api = fixtures("00401000", "RAM:0x401000;DROP")
        with self.assertRaisesRegex(ValueError, "function address"):
            correlate(idf, api, SHA)

    def test_unresolved_function_is_not_counted(self):
        idf, api = fixtures(None, "00401000")
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_referencing_functions"], 0)
        self.assertEqual(result["shared_idf_and_api_functions"], 0)


if __name__ == "__main__":
    unittest.main()
