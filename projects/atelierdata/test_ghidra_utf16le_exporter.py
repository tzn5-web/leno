"""Regression: exporter emits :utf16le, not :utf16."""
import unittest
from ghidra_idf_api_correlation import correlate

SHA = "a" * 64

class Utf16LEExporterRegression(unittest.TestCase):
    def test_real_exporter_suffix_is_counted(self):
        base = {"source_sha256": SHA, "executed_target_binary": False,
                "idf_decoder_proven": False}
        idf = dict(base, keyword_hits={"block": {
            "MODELS.IDF:utf16le": [{"references_from": [
                {"function_entry": "00401000"}]}]}})
        api = dict(base, schema="atelierdata-ghidra-file-api-xrefs-v1",
                   api_symbols={})
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_reference_count"], 1)
        self.assertEqual(result["idf_distinct_filenames_with_xrefs"], 1)
        self.assertEqual(result["idf_referencing_functions"], 1)

    def test_non_idf_extension_is_not_counted(self):
        base = {"source_sha256": SHA, "executed_target_binary": False,
                "idf_decoder_proven": False}
        idf = dict(base, keyword_hits={"block": {
            "MODELS.IDF.bak:utf16le": [{"references_from": [
                {"function_entry": "00401000"}]}]}})
        api = dict(base, schema="atelierdata-ghidra-file-api-xrefs-v1",
                   api_symbols={})
        result = correlate(idf, api, SHA)
        self.assertEqual(result["idf_reference_count"], 0)

if __name__ == "__main__":
    unittest.main()
