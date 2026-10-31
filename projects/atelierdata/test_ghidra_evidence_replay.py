"""Synthetic-only tests for SHA256-gated Ghidra evidence replay."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ghidra_evidence_replay import replay, _atomic_json
from pe_loadlibrary_literals import analyze
from test_pe_loadlibrary_literals import fake_pe


def fixture():
    pe = fake_pe()
    digest = hashlib.sha256(pe).hexdigest()
    _, triage = analyze(pe, digest)
    call = triage["candidates"][0]["call_va"]
    report = {
        "schema": "atelierdata-ghidra-loadlibrary-private-v1",
        "source_sha256": digest,
        "source_md5": hashlib.md5(pe).hexdigest(),
        "ghidra_executable_md5_verified": True,
        "candidate_count": 1,
        "recognized_instruction_pairs": 1,
        "verified_literal_pointers": 1,
        "iat_references": 0,
        "verified_candidates_in_direct_call_graph": 0,
        "ghidra_declared_entry_roots_with_functions": 0,
        "direct_call_graph_functions_visited": 0,
        "direct_call_graph_complete_within_budget": True,
        "target_executed": False,
        "cfg_reachability_proven": False,
        "idf_decoder_proven": False,
        "candidates": [{
            "call_va": call,
            "push_call_instruction_verified": True,
            "literal_pointer_verified": True,
            "ghidra_reference_to_iat": False,
            "in_ghidra_entrypoint_direct_call_graph": False,
            "containing_function": None
        }]
    }
    return pe, digest, triage, report


class EvidenceReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "synthetic.exe"
        self.pe, self.sha, self.triage, self.report = fixture()
        self.path.write_bytes(self.pe)

    def test_verified_replay_only_aggregate(self):
        result = replay(self.path, self.sha, self.triage, self.report)
        self.assertEqual(result["candidate_count"], 1)
        self.assertTrue(result["pe_sha256_independently_reverified"])
        self.assertTrue(result["private_triage_exactly_replayed"])
        self.assertFalse(result["idf_decoder_proven"])
        self.assertFalse(result["original_executed_by_replay"])
        self.assertNotIn("example.dll", json.dumps(result))
        self.assertNotIn("call_va", json.dumps(result))

    def test_rejects_tampered_private_triage(self):
        self.triage["candidates"][0]["literal"] = "tampered.dll"
        with self.assertRaisesRegex(ValueError, "differs"):
            replay(self.path, self.sha, self.triage, self.report)

    def test_rejects_missing_candidate(self):
        self.triage["candidates"] = []
        with self.assertRaises(ValueError):
            replay(self.path, self.sha, self.triage, self.report)

    def test_rejects_wrong_ghidra_binary_md5(self):
        self.report["source_md5"] = "0" * 32
        with self.assertRaisesRegex(ValueError, "Mismatched original identity"):
            replay(self.path, self.sha, self.triage, self.report)

    def test_rejects_tampered_ghidra_report(self):
        self.report["verified_literal_pointers"] = 0
        with self.assertRaises(ValueError):
            replay(self.path, self.sha, self.triage, self.report)

    def test_rejects_wrong_pe_sha256(self):
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            replay(self.path, "0" * 64, self.triage, self.report)

    def test_rejects_modified_pe(self):
        self.path.write_bytes(self.pe + b"changed")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            replay(self.path, self.sha, self.triage, self.report)

    def test_rejects_symlink_pe(self):
        linked = self.path.with_name("linked.exe")
        try:
            linked.symlink_to(self.path)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable")
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            replay(linked, self.sha, self.triage, self.report)

    def test_atomic_public_report_has_no_private_strings(self):
        summary = replay(self.path, self.sha, self.triage, self.report)
        output = self.path.with_suffix(".json")
        _atomic_json(output, summary)
        content = output.read_text(encoding="utf-8")
        self.assertNotIn("example.dll", content)
        self.assertTrue(json.loads(content)["pe_sha256_independently_reverified"])


if __name__ == "__main__":
    unittest.main()
