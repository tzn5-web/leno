"""Synthetic PE-only tests; never use private original files in public CI."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ghidra_iat_source_replay import replay
from ghidra_iat_consistency import write_aggregate
from test_ghidra_iat_consistency import fixture
from test_pe_file_io_xrefs import sample_pe


class GhidraIatSourceReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pe = Path(self.temp.name) / "synthetic.exe"
        self.data = sample_pe()
        self.pe.write_bytes(self.data)
        self.sha = hashlib.sha256(self.data).hexdigest()
        self.triage, self.ghidra = fixture()

    def test_independent_replay_and_redaction(self):
        summary = replay(self.pe, self.sha, self.triage, self.ghidra)
        self.assertTrue(summary["pe_sha256_independently_reverified"])
        self.assertTrue(summary["private_iat_triage_exactly_replayed"])
        self.assertFalse(summary["idf_decoder_proven"])
        destination = Path(self.temp.name) / "public.json"
        write_aggregate(destination, summary)
        text = destination.read_text(encoding="utf-8")
        self.assertNotIn("PRIVATE_ADDRESS", text)
        self.assertNotIn("PRIVATE_FUNCTION", text)
        self.assertNotIn("instruction_va", text)
        self.assertNotIn("iat_va", text)

    def test_tampered_private_candidate_rejected(self):
        altered = copy.deepcopy(self.triage)
        altered["candidates"][0]["symbol"] = "ReadFile"
        with self.assertRaisesRegex(ValueError, "triage differs"):
            replay(self.pe, self.sha, altered, self.ghidra)

    def test_tampered_private_md5_rejected(self):
        altered = copy.deepcopy(self.triage)
        altered["md5"] = "0" * 32
        with self.assertRaisesRegex(ValueError, "triage differs"):
            replay(self.pe, self.sha, altered, self.ghidra)

    def test_tampered_private_literal_offsets_rejected(self):
        altered = copy.deepcopy(self.triage)
        altered["literal_locations"] = []
        with self.assertRaisesRegex(ValueError, "triage differs"):
            replay(self.pe, self.sha, altered, self.ghidra)

    def test_changed_pe_rejected_by_sha256(self):
        self.pe.write_bytes(self.data + b"X")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            replay(self.pe, self.sha, self.triage, self.ghidra)

    def test_wrong_expected_sha256_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA256"):
            replay(self.pe, "0" * 64, self.triage, self.ghidra)

    def test_ghidra_forged_reference_rejected(self):
        altered = copy.deepcopy(self.ghidra)
        altered["candidates"][0]["iat_va"] += 4
        with self.assertRaisesRegex(ValueError, "Candidate identity"):
            replay(self.pe, self.sha, self.triage, altered)

    def test_oversized_pe_rejected_before_read(self):
        with self.pe.open("ab") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(ValueError, "size bound"):
            replay(self.pe, self.sha, self.triage, self.ghidra)

    def test_missing_pe_rejected(self):
        self.pe.unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            replay(self.pe, self.sha, self.triage, self.ghidra)

    def test_symlink_pe_rejected_when_supported(self):
        link = Path(self.temp.name) / "alias.exe"
        try:
            link.symlink_to(self.pe)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable")
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            replay(link, self.sha, self.triage, self.ghidra)


if __name__ == "__main__":
    unittest.main()
