"""Synthetic-only regression tests; no proprietary binaries or data."""
import copy
import hashlib
import json
import struct
import unittest

from ghidra_idf_reference_site_audit import audit
from test_ghidra_idf_xref_verify import fixture


def with_push():
    data, sha, private, public = fixture()
    buf = bytearray(data)
    buf[0x220:0x225] = b"\x68" + struct.pack("<I", 0x401060)
    data = bytes(buf)
    sha = hashlib.sha256(data).hexdigest()
    private["original_sha256_verified"] = sha
    public["original_sha256_verified"] = sha
    return data, sha, private, public


class ReferenceSiteAuditTests(unittest.TestCase):
    def test_synthetic_code_pointer_nearby(self):
        data, sha, private, public = with_push()
        report = audit(data, sha, private, public)
        self.assertEqual(report["sources_in_executable_raw_sections"], 1)
        self.assertEqual(report["executable_sources_with_nearby_raw_literal_va"], 1)
        self.assertEqual(report["reported_reference_sites_inspected"], 1)
        self.assertFalse(report["idf_decoder_proven"])
        self.assertFalse(report["ghidra_disassembly_independently_verified"])
        self.assertNotIn("004010", json.dumps(report))
        self.assertNotIn("file_offset", json.dumps(report))

    def test_original_fixture_without_pointer_is_not_false_positive(self):
        data, sha, private, public = fixture()
        report = audit(data, sha, private, public)
        self.assertEqual(report["sources_in_executable_raw_sections"], 1)
        self.assertEqual(report["executable_sources_with_nearby_raw_literal_va"], 0)

    def test_unmapped_reference_is_counted_not_assumed_real(self):
        data, sha, private, public = fixture()
        private["hits_with_addresses"][".IDF:ascii"][0]["references_from"] = ["00ABCDEF"]
        report = audit(data, sha, private, public)
        self.assertEqual(report["sources_unmapped_to_raw_file"], 1)
        self.assertEqual(report["sources_in_executable_raw_sections"], 0)

    def test_invalid_reference_address_rejected(self):
        data, sha, private, public = fixture()
        private["hits_with_addresses"][".IDF:ascii"][0]["references_from"] = ["not-a-va"]
        with self.assertRaisesRegex(ValueError, "Invalid Ghidra reference"):
            audit(data, sha, private, public)

    def test_reference_from_data_section_classified(self):
        data, sha, private, public = fixture()
        private["hits_with_addresses"][".IDF:ascii"][0]["references_from"] = ["00402010"]
        report = audit(data, sha, private, public)
        self.assertEqual(report["sources_in_nonexecutable_raw_sections"], 1)

    def test_duplicate_sources_counted_without_inventing_xrefs(self):
        data, sha, private, public = fixture()
        row = private["hits_with_addresses"][".IDF:ascii"][0]
        row["reference_count"] = 2
        row["references_from"] = ["00401020", "00401020"]
        private["patterns"][".IDF:ascii"]["ghidra_existing_references"] = 2
        public["patterns"][".IDF:ascii"]["ghidra_existing_references"] = 2
        report = audit(data, sha, private, public)
        self.assertEqual(report["unique_source_repetitions"], 1)
        self.assertEqual(report["reported_reference_sites_inspected"], 2)

    def test_sha_mismatch_rejected(self):
        data, sha, private, public = fixture()
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            audit(data, "0" * 64, private, public)

    def test_public_report_tampering_rejected(self):
        data, sha, private, public = fixture()
        public["patterns"][".IDF:ascii"]["ghidra_existing_references"] = 42
        with self.assertRaisesRegex(ValueError, "disagree"):
            audit(data, sha, private, public)

    def test_reports_not_modified(self):
        data, sha, private, public = fixture()
        before = copy.deepcopy(private)
        audit(data, sha, private, public)
        self.assertEqual(before, private)


if __name__ == "__main__":
    unittest.main()
