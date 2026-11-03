"""Synthetic regression for cross-report source identity; no private files."""
import unittest
from ghidra_idf_api_correlation import correlate

SHA = "a" * 64

def reports():
    common = {"source_sha256": SHA, "target_executed": False,
              "idf_decoder_proven": False}
    idf = dict(common, keyword_hits={}, source_md5="1" * 32)
    api = dict(common, schema="atelierdata-ghidra-file-api-xrefs-v1",
               api_symbols={}, source_md5="1" * 32)
    return idf, api

class TestSourceMd5Consistency(unittest.TestCase):
    def test_matching_identity(self):
        idf, api = reports()
        self.assertTrue(correlate(idf, api, SHA)["source_sha256_claims_match"])

    def test_conflicting_identity_rejected(self):
        idf, api = reports()
        api["source_md5"] = "2" * 32
        with self.assertRaisesRegex(ValueError, "disagree"):
            correlate(idf, api, SHA)

    def test_invalid_identity_rejected(self):
        idf, api = reports()
        api["source_md5"] = "not-md5"
        with self.assertRaisesRegex(ValueError, "Invalid"):
            correlate(idf, api, SHA)

    def test_legacy_missing_identity(self):
        idf, api = reports()
        del api["source_md5"]
        self.assertEqual(correlate(idf, api, SHA)["idf_reference_count"], 0)

if __name__ == "__main__":
    unittest.main()
