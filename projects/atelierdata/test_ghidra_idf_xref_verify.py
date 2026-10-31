"""Synthetic PE32 tests; no Autodata binary or proprietary data in CI."""
import copy
import hashlib
import json
import unittest
from pathlib import Path

from ghidra_idf_xref_verify import TERMS, verify
from test_pe_file_io_xrefs import sample_pe

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "ghidra" / "AtelierData_IDF_Xrefs_Verified.java"


def fixture():
    data = bytearray(sample_pe())
    data[0x260:0x264] = b".IDF"
    data = bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    patterns = {
        term + ":" + encoding: {
            "hits_at_most_32": 0, "hit_cap_reached": False,
            "ghidra_existing_references": 0,
            "ghidra_existing_code_references": 0,
        }
        for term in TERMS for encoding in ("ascii", "utf16le")
    }
    patterns[".IDF:ascii"] = {
        "hits_at_most_32": 1, "hit_cap_reached": False,
        "ghidra_existing_references": 1,
        "ghidra_existing_code_references": 1,
    }
    public = {
        "schema": "atelierdata-ghidra-idf-xrefs-public-v1",
        "original_sha256_verified": digest,
        "ghidra_program_md5_verified": True,
        "initialized_blocks": 2,
        "scanned_bytes": 1024,
        "scan_truncated": False,
        "patterns": patterns,
        "target_executed": False,
        "idf_decoder_proven": False,
        "limitations": "Synthetic evidence only.",
    }
    private = copy.deepcopy(public)
    private["schema"] = "atelierdata-ghidra-idf-xrefs-private-v1"
    private["private_only"] = True
    private["hits_with_addresses"] = {
        ".IDF:ascii": [{
            "address": "00401060",
            "reference_count": 1,
            "code_reference_count": 1,
            "references_from_truncated": False,
            "references_from": ["00401020"],
        }]
    }
    return data, digest, private, public


class VerifiedGhidraIDFEvidenceTests(unittest.TestCase):
    def test_verified_synthetic_literal(self):
        data, sha, private, public = fixture()
        result = verify(data, sha, private, public)
        self.assertEqual(result["verified_literal_hits"], 1)
        self.assertEqual(result["ghidra_claimed_code_references"], 1)
        self.assertFalse(result["idf_decoder_proven"])
        self.assertNotIn("00401060", json.dumps(result))

    def test_original_sha_tamper_rejected(self):
        data, sha, private, public = fixture()
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            verify(data + b"x", sha, private, public)

    def test_literal_address_tamper_rejected(self):
        data, sha, private, public = fixture()
        private["hits_with_addresses"][".IDF:ascii"][0]["address"] = "00401061"
        with self.assertRaisesRegex(ValueError, "literal does not match"):
            verify(data, sha, private, public)

    def test_unmapped_address_rejected(self):
        data, sha, private, public = fixture()
        private["hits_with_addresses"][".IDF:ascii"][0]["address"] = "00999999"
        with self.assertRaisesRegex(ValueError, "no unique PE raw mapping"):
            verify(data, sha, private, public)

    def test_public_aggregate_tamper_rejected(self):
        data, sha, private, public = fixture()
        public["patterns"][".IDF:ascii"]["ghidra_existing_code_references"] = 9
        with self.assertRaisesRegex(ValueError, "disagree"):
            verify(data, sha, private, public)

    def test_private_reference_tamper_rejected(self):
        data, sha, private, public = fixture()
        private["hits_with_addresses"][".IDF:ascii"][0]["code_reference_count"] = 2
        with self.assertRaisesRegex(ValueError, "Inconsistent"):
            verify(data, sha, private, public)

    def test_private_duplicate_hit_rejected(self):
        data, sha, private, public = fixture()
        private["hits_with_addresses"][".IDF:ascii"] *= 2
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            verify(data, sha, private, public)

    def test_incorrect_ghidra_program_flag_rejected(self):
        data, sha, private, public = fixture()
        private["ghidra_program_md5_verified"] = False
        public["ghidra_program_md5_verified"] = False
        with self.assertRaisesRegex(ValueError, "identity or safety"):
            verify(data, sha, private, public)

    def test_source_contract_identity_privacy_and_scan_bounds(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('MessageDigest.getInstance("SHA-256")', src)
        self.assertIn("currentProgram.getExecutableMD5()", src)
        self.assertIn("source.equals(privateOutput)", src)
        self.assertIn("source.equals(publicOutput)", src)
        self.assertIn("MAX_SCAN_TOTAL", src)
        self.assertIn("getInstructionContaining", src)
        self.assertIn("privateReport.put(\"hits_with_addresses\"", src)
        self.assertNotIn('publicReport.put("hits_with_addresses"', src)
        self.assertIn("idf_decoder_proven", src)


if __name__ == "__main__":
    unittest.main()
