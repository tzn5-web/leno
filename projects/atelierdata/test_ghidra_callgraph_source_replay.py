"""Synthetic-only regression tests for independent PE32 E8 rel32 callgraph replay."""
import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from ghidra_callgraph_source_replay import replay
from test_pe_file_io_xrefs import sample_pe


def fixture():
    binary = bytearray(sample_pe())
    # .text starts at raw offset 0x200 / VA 0x401000.
    site, callee = 0x401020, 0x401060
    binary[0x220:0x225] = b"\xe8" + struct.pack("<i", callee - site - 5)
    binary = bytes(binary)
    sha = hashlib.sha256(binary).hexdigest()
    graph = {
        "schema": "atelierdata-ghidra-direct-callgraph-v2",
        "edge_verification": "x86-e8-rel32-ghidra-bytes-v1",
        "source_sha256": sha, "source_md5": hashlib.md5(binary).hexdigest(),
        "source_sha256_verified": True,
        "ghidra_import_sha256_verified": True,
        "ghidra_import_md5_verified": True,
        "target_executed": False, "idf_decoder_proven": False,
        "coverage_truncated": False,
        "edges": [{
            "caller": "00401000", "callee": "00401060", "site": "00401020",
            "reference_type": "UNCONDITIONAL_CALL",
            "instruction_mnemonic": "CALL", "instruction_length": 5,
            "direct_rel32_opcode_verified": True,
            "source_executable": True, "target_executable": True,
        }],
    }
    return binary, sha, graph


class SourceReplayTests(unittest.TestCase):
    def test_verified_synthetic_rel32(self):
        binary, sha, graph = fixture()
        result = replay(binary, sha, graph)
        self.assertEqual(result["direct_call_sites_verified"], 1)
        self.assertTrue(result["all_reported_call_edges_replayed_against_original_pe"])
        self.assertFalse(result["idf_decoder_proven"])
        self.assertNotIn("004010", json.dumps(result))

    def test_original_bytes_changed_but_metadata_unchanged(self):
        binary, sha, graph = fixture()
        tampered = bytearray(binary)
        tampered[0x220] = 0x90
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            replay(bytes(tampered), sha, graph)

    def test_forged_edge_target_rejected(self):
        binary, sha, graph = fixture()
        graph["edges"][0]["callee"] = "00401061"
        with self.assertRaisesRegex(ValueError, "destination mismatch"):
            replay(binary, sha, graph)

    def test_forged_edge_site_rejected(self):
        binary, sha, graph = fixture()
        graph["edges"][0]["site"] = "00401021"
        with self.assertRaisesRegex(ValueError, "not E8 rel32"):
            replay(binary, sha, graph)

    def test_unmapped_padding_rejected(self):
        binary, sha, graph = fixture()
        modified = bytearray(binary)
        # Section has 0x200 raw bytes but only 0x20 virtual bytes.
        struct.pack_into("<I", modified, 0x180, 0x20)
        modified = bytes(modified)
        graph["source_sha256"] = hashlib.sha256(modified).hexdigest()
        graph["source_md5"] = hashlib.md5(modified).hexdigest()
        with self.assertRaisesRegex(ValueError, "not uniquely backed"):
            replay(modified, graph["source_sha256"], graph)

    def test_wrong_ghidra_md5_rejected(self):
        binary, sha, graph = fixture()
        graph["source_md5"] = "0" * 32
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            replay(binary, sha, graph)

    def test_missing_ghidra_identity_rejected(self):
        binary, sha, graph = fixture()
        graph["ghidra_import_md5_verified"] = False
        with self.assertRaisesRegex(ValueError, "identity verification"):
            replay(binary, sha, graph)

    def test_false_decoder_claim_rejected(self):
        binary, sha, graph = fixture()
        graph["idf_decoder_proven"] = True
        with self.assertRaisesRegex(ValueError, "decoder claim"):
            replay(binary, sha, graph)

    def test_unsupported_edge_contract_rejected(self):
        binary, sha, graph = fixture()
        graph["edge_verification"] = "legacy"
        with self.assertRaisesRegex(ValueError, "edge verification"):
            replay(binary, sha, graph)

    def test_non_executable_section_rejected(self):
        binary, sha, graph = fixture()
        modified = bytearray(binary)
        struct.pack_into("<I", modified, 0x19c, 0x40000040)
        modified = bytes(modified)
        graph["source_sha256"] = hashlib.sha256(modified).hexdigest()
        graph["source_md5"] = hashlib.md5(modified).hexdigest()
        with self.assertRaisesRegex(ValueError, "not uniquely backed"):
            replay(modified, graph["source_sha256"], graph)


if __name__ == "__main__":
    unittest.main()
