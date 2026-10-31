"""Synthetic-only tests; no proprietary Autodata bytes or metadata."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from original_chunk_chain_gate import CHUNK_BYTES, audit_manifest

ROOT = "Autodata__3.45/ADCDA2/"


def row(name, chunks):
    return {"path": ROOT + name, "size_bytes": sum(c["bytes"] for c in chunks), "chunks": chunks}


def chunk(name, size, part=1):
    return {"package": f"autodata_part_{part:04d}.zip", "entry": ROOT + name,
            "bytes": size, "sha256": hashlib.sha256(name.encode()).hexdigest()}


def fixture():
    single = row("ADBCD.exe", [chunk("ADBCD.exe", 10)])
    name = "COMMON/SYNTHETIC.IDF"
    multi = row(name, [chunk(name + ".chunk0000", CHUNK_BYTES),
                       chunk(name + ".chunk0001", 7, 2)])
    return {"file_count": 2, "package_count": 2,
            "total_extracted_bytes": single["size_bytes"] + multi["size_bytes"],
            "files": [single, multi]}


class ChunkChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "inventory.json"
        self.data = fixture()

    def check(self, expected="PASS"):
        self.path.write_text(json.dumps(self.data), encoding="utf-8")
        result = audit_manifest(self.path)
        self.assertEqual(result["chain_structure"], expected)
        return result

    def test_valid_chain_counts(self):
        r = self.check()
        self.assertEqual((r["manifest_chunk_count"], r["multipart_chunk_count"]), (3, 2))
        self.assertEqual(r["idf_files_requiring_blocked_package"], 0)
        self.assertFalse(r["zip_payloads_opened"])

    def test_single_member_wrong_entry(self):
        self.data["files"][0]["chunks"][0]["entry"] += ".wrong"
        self.assertIn("single_member_entry_name_mismatch", self.check("FAIL")["structural_failures"])

    def test_missing_chunk_index(self):
        self.data["files"][1]["chunks"][1]["entry"] = ROOT + "COMMON/SYNTHETIC.IDF.chunk0002"
        self.assertIn("multipart_sequence_name_or_order_mismatch", self.check("FAIL")["structural_failures"])

    def test_reordered_chunks(self):
        self.data["files"][1]["chunks"].reverse()
        self.assertIn("multipart_sequence_name_or_order_mismatch", self.check("FAIL")["structural_failures"])

    def test_nonfinal_chunk_size(self):
        self.data["files"][1]["chunks"][0]["bytes"] = 12
        self.data["files"][1]["size_bytes"] = 19
        self.data["total_extracted_bytes"] = 29
        self.assertIn("nonfinal_chunk_size_mismatch", self.check("FAIL")["structural_failures"])

    def test_final_chunk_zero(self):
        self.data["files"][1]["chunks"][1]["bytes"] = 0
        self.data["files"][1]["size_bytes"] = CHUNK_BYTES
        self.data["total_extracted_bytes"] = CHUNK_BYTES + 10
        self.assertIn("final_chunk_size_out_of_bounds", self.check("FAIL")["structural_failures"])

    def test_package_order_regression(self):
        self.data["files"][1]["chunks"][0]["package"] = "autodata_part_0002.zip"
        self.data["files"][1]["chunks"][1]["package"] = "autodata_part_0001.zip"
        self.assertIn("package_order_regression", self.check("FAIL")["structural_failures"])

    def test_declared_size_mismatch(self):
        self.data["total_extracted_bytes"] += 1
        self.assertIn("declared_total_bytes_mismatch", self.check("FAIL")["structural_failures"])

    def test_blocked_package_is_only_counted_not_opened(self):
        self.data["files"][1]["chunks"][1]["package"] = "autodata_part_0016.zip"
        r = self.check()
        self.assertEqual(r["blocked_package_chunk_count"], 1)
        self.assertEqual(r["idf_files_requiring_blocked_package"], 1)
        self.assertFalse(r["zip_payloads_opened"])

    def test_duplicate_entry_rejected_by_manifest_loader(self):
        self.data["files"][1]["chunks"][1]["entry"] = self.data["files"][1]["chunks"][0]["entry"]
        self.data["files"][1]["chunks"][1]["package"] = "autodata_part_0001.zip"
        self.data["package_count"] = 1
        self.path.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaises(ValueError):
            audit_manifest(self.path)

    def test_invalid_manifest_path_rejected(self):
        self.data["files"][0]["path"] = ROOT + "../BAD.exe"
        self.path.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaises(ValueError):
            audit_manifest(self.path)


if __name__ == "__main__":
    unittest.main()
