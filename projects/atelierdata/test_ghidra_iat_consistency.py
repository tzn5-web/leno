"""Synthetic-only regression tests for the Ghidra IAT evidence verifier."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ghidra_iat_consistency import validate, write_aggregate, load_private
from pe_file_io_xrefs import analyze
from test_pe_file_io_xrefs import sample_pe


def fixture():
    pe = sample_pe()
    _, triage = analyze(pe, hashlib.sha256(pe).hexdigest())
    item = triage["candidates"][0]
    ghidra = {
        "schema": "atelierdata-ghidra-iat-instruction-check-v1",
        "source_sha256": triage["sha256"],
        "source_md5": triage["md5"],
        "ghidra_executable_md5_verified": True,
        "target_executed": False,
        "idf_decoder_proven": False,
        "candidate_count": 1,
        "recognized_instruction_count": 1,
        "instructions_with_references": 1,
        "references_to_expected_iat": 1,
        "candidates": [{
            "instruction_va": item["instruction_va"],
            "address": "PRIVATE_ADDRESS",
            "symbol": item["symbol"],
            "kind": item["kind"],
            "iat_va": item["iat_va"],
            "in_memory": True,
            "recognized_instruction": True,
            "mnemonic": "CALL",
            "references_from_instruction": 1,
            "reference_to_expected_iat": True,
            "containing_function": "PRIVATE_FUNCTION",
        }]
    }
    return triage, ghidra


class GhidraIatConsistencyTests(unittest.TestCase):
    def test_valid_private_report_aggregate_redacted(self):
        triage, report = fixture()
        summary = validate(triage, report)
        self.assertEqual(summary["recognized_instruction_count"], 1)
        self.assertEqual(summary["references_to_expected_iat"], 1)
        self.assertFalse(summary["idf_decoder_proven"])
        encoded = json.dumps(summary)
        self.assertNotIn("PRIVATE_FUNCTION", encoded)
        self.assertNotIn("PRIVATE_ADDRESS", encoded)
        self.assertNotIn("LoadLibraryA", encoded)
        self.assertNotIn("iat_va", encoded)

    def test_wrong_imported_pe_md5_rejected(self):
        triage, report = fixture()
        report["source_md5"] = "0" * 32
        with self.assertRaisesRegex(ValueError, "identity"):
            validate(triage, report)

    def test_unverified_imported_pe_rejected(self):
        triage, report = fixture()
        report["ghidra_executable_md5_verified"] = False
        with self.assertRaisesRegex(ValueError, "identity"):
            validate(triage, report)

    def test_wrong_sha256_rejected(self):
        triage, report = fixture()
        report["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "identity"):
            validate(triage, report)

    def test_wrong_iat_pointer_rejected(self):
        triage, report = fixture()
        report["candidates"][0]["iat_va"] += 4
        with self.assertRaisesRegex(ValueError, "Candidate identity"):
            validate(triage, report)

    def test_wrong_symbol_rejected(self):
        triage, report = fixture()
        report["candidates"][0]["symbol"] = "ReadFile"
        with self.assertRaisesRegex(ValueError, "Candidate identity"):
            validate(triage, report)

    def test_unrecognized_reference_rejected(self):
        triage, report = fixture()
        report["candidates"][0]["recognized_instruction"] = False
        with self.assertRaisesRegex(ValueError, "Contradictory"):
            validate(triage, report)

    def test_inconsistent_reference_count_rejected(self):
        triage, report = fixture()
        report["candidates"][0]["references_from_instruction"] = 0
        with self.assertRaisesRegex(ValueError, "Contradictory"):
            validate(triage, report)

    def test_aggregate_tampering_rejected(self):
        triage, report = fixture()
        report["recognized_instruction_count"] = 2
        with self.assertRaisesRegex(ValueError, "Aggregate"):
            validate(triage, report)

    def test_invalid_boolean_rejected(self):
        triage, report = fixture()
        report["candidates"][0]["in_memory"] = 1
        with self.assertRaisesRegex(ValueError, "Boolean"):
            validate(triage, report)

    def test_missing_candidate_rejected(self):
        triage, report = fixture()
        report["candidates"] = []
        report["candidate_count"] = 0
        with self.assertRaisesRegex(ValueError, "Candidate count"):
            validate(triage, report)

    def test_private_io_and_public_atomic_output(self):
        triage, report = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "private.json"
            source.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(load_private(source), report)
            public = root / "aggregate.json"
            write_aggregate(public, validate(triage, report))
            data = public.read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE_FUNCTION", data)
            self.assertNotIn("LoadLibraryA", data)
            self.assertTrue(json.loads(data)["ghidra_import_md5_checked"])


if __name__ == "__main__":
    unittest.main()
