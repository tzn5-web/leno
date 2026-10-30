"""Synthetic regression tests for PE IAT evidence provenance; no proprietary data."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from pe_file_io_xrefs import analyze
from pe_iat_evidence_validate import verify_evidence, run
from test_pe_file_io_xrefs import sample_pe


def fixture():
    data = sample_pe()
    digest = hashlib.sha256(data).hexdigest()
    _public, private = analyze(data, digest)
    return data, digest, private


def ghidra_fixture(report, digest, recognized=True):
    checks = []
    for row in report["candidates"]:
        checks.append({
            "instruction_va": row["instruction_va"],
            "iat_va": row["iat_va"],
            "symbol": row["symbol"],
            "kind": row["kind"],
            "instruction_opcode_operand_verified": recognized,
            "ghidra_reference_to_iat": recognized,
        })
    return {
        "schema": "atelierdata-ghidra-iat-private-v2",
        "original_sha256_verified": digest,
        "ghidra_program_md5_verified": True,
        "candidate_count": len(checks),
        "opcode_operand_verified": len(checks) if recognized else 0,
        "ghidra_references_to_iat": len(checks) if recognized else 0,
        "candidates": checks,
    }


class EvidenceValidationTests(unittest.TestCase):
    def test_verified_original_bytes_and_public_redaction(self):
        data, digest, report = fixture()
        public = verify_evidence(data, report, digest)
        self.assertEqual(public["candidate_count"], 1)
        self.assertEqual(public["call_candidate_count"], 1)
        self.assertTrue(public["candidate_report_matches_independent_rescan"])
        self.assertNotIn("LoadLibraryA", json.dumps(public))
        self.assertNotIn("file_offset", json.dumps(public))
        self.assertFalse(public["idf_decoder_proven"])

    def test_wrong_original_hash(self):
        data, _, report = fixture()
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            verify_evidence(data, report, "0" * 64)

    def test_forged_report_digest(self):
        data, digest, report = fixture()
        report["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "schema or SHA256"):
            verify_evidence(data, report, digest)

    def test_forged_address(self):
        data, digest, report = fixture()
        report["candidates"][0]["instruction_va"] += 1
        with self.assertRaisesRegex(ValueError, "disagrees"):
            verify_evidence(data, report, digest)

    def test_forged_offset(self):
        data, digest, report = fixture()
        report["candidates"][0]["file_offset"] += 1
        with self.assertRaisesRegex(ValueError, "disagrees"):
            verify_evidence(data, report, digest)

    def test_forged_iat_operand(self):
        data, digest, report = fixture()
        report["candidates"][0]["iat_va"] += 4
        with self.assertRaisesRegex(ValueError, "disagrees"):
            verify_evidence(data, report, digest)

    def test_forged_import_symbol(self):
        data, digest, report = fixture()
        report["candidates"][0]["symbol"] = "CreateFileA"
        with self.assertRaisesRegex(ValueError, "disagrees"):
            verify_evidence(data, report, digest)

    def test_duplicate_candidate_rejected(self):
        data, digest, report = fixture()
        report["candidates"].append(copy.deepcopy(report["candidates"][0]))
        with self.assertRaisesRegex(ValueError, "count differs"):
            verify_evidence(data, report, digest)

    def test_missing_candidate_rejected(self):
        data, digest, report = fixture()
        report["candidates"].clear()
        with self.assertRaisesRegex(ValueError, "count differs"):
            verify_evidence(data, report, digest)

    def test_non_integer_boolean_address_rejected(self):
        data, digest, report = fixture()
        report["candidates"][0]["file_offset"] = True
        with self.assertRaises(ValueError):
            verify_evidence(data, report, digest)

    def test_ghidra_identity_and_counts_consistent(self):
        data, digest, report = fixture()
        ghidra = ghidra_fixture(report, digest)
        public = verify_evidence(data, report, digest, ghidra)
        self.assertEqual(public["ghidra_report_claimed_verified_instructions"], 1)
        self.assertTrue(public["ghidra_report_identity_consistent"])

    def test_ghidra_mismatched_candidate_rejected(self):
        data, digest, report = fixture()
        ghidra = ghidra_fixture(report, digest)
        ghidra["candidates"][0]["iat_va"] += 4
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            verify_evidence(data, report, digest, ghidra)

    def test_ghidra_inconsistent_aggregate_rejected(self):
        data, digest, report = fixture()
        ghidra = ghidra_fixture(report, digest)
        ghidra["opcode_operand_verified"] = 0
        with self.assertRaisesRegex(ValueError, "aggregate counts"):
            verify_evidence(data, report, digest, ghidra)

    def test_ghidra_reference_requires_instruction(self):
        data, digest, report = fixture()
        ghidra = ghidra_fixture(report, digest, recognized=False)
        ghidra["candidates"][0]["ghidra_reference_to_iat"] = True
        with self.assertRaisesRegex(ValueError, "reference without"):
            verify_evidence(data, report, digest, ghidra)

    def test_output_isolation_and_valid_cli_run(self):
        data, digest, report = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, detail, output = root / "original.exe", root / "iat-private.json", root / "summary.json"
            source.write_bytes(data)
            detail.write_text(json.dumps(report), encoding="utf-8")
            result = run(source, digest, detail, output)
            self.assertEqual(result["candidate_count"], 1)
            self.assertNotIn("LoadLibraryA", output.read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, "must differ"):
                run(source, digest, detail, source)
            with self.assertRaisesRegex(ValueError, "must differ"):
                run(source, digest, detail, detail)
            self.assertEqual(source.read_bytes(), data)

    def test_corrupt_json_rejected_without_output(self):
        data, digest, _ = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, detail, output = root / "original.exe", root / "private.json", root / "public.json"
            source.write_bytes(data)
            detail.write_text("{bad-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid private JSON"):
                run(source, digest, detail, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
