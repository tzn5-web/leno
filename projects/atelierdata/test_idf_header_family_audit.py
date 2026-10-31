"""Synthetic-only regression tests; no proprietary IDF samples included."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from idf_header_family_audit import analyze, run


def fixture():
    rows = [
        "path,category,header64_hex,sample_entropy",
        "PRIVATE_ALPHA.IDF,idf,00112233445566778899aabbccddeeff,7.9",
        "PRIVATE_BETA.IDF,idf,00112233445566778899aabbccddeeff,7.8",
        "PRIVATE_GAMMA.IDF,idf,00112233aabbccdd00112233aabbccdd,7.7",
        "PRIVATE_OTHER.DAT,other,0011223344556677,4.0",
        "PRIVATE_SHORT.IDF,idf,aa,1.0",
    ]
    raw = ("\n".join(rows) + "\n").encode()
    return raw, hashlib.sha256(raw).hexdigest()


class HeaderFamilyTests(unittest.TestCase):
    def test_exact_prefix_counts_and_short_samples(self):
        raw, digest = fixture()
        result = analyze(raw, digest)
        self.assertEqual(result["idf_records"], 4)
        self.assertEqual(result["headers_shorter_than_32_bytes"], 4)
        self.assertEqual(result["prefix_clusters_by_bytes"]["4"]["group_sizes"], [3])
        self.assertEqual(result["prefix_clusters_by_bytes"]["8"]["group_sizes"], [2])
        self.assertEqual(result["prefix_clusters_by_bytes"]["32"]["multi_file_groups"], 0)
        self.assertEqual(result["sample_entropy_at_least_7_9"], 1)

    def test_public_output_does_not_expose_headers_or_paths(self):
        raw, digest = fixture()
        serialized = json.dumps(analyze(raw, digest))
        self.assertNotIn("PRIVATE_", serialized)
        self.assertNotIn("001122334455", serialized)
        self.assertFalse(json.loads(serialized)["idf_decoding_proven"])

    def test_digest_mismatch_rejected(self):
        raw, _ = fixture()
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            analyze(raw, "0" * 64)

    def test_duplicate_path_rejected(self):
        raw, _ = fixture()
        raw += b"PRIVATE_ALPHA.IDF,idf,ab,1.0\n"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            analyze(raw, hashlib.sha256(raw).hexdigest())

    def test_bad_header_rejected(self):
        raw = b"path,category,header64_hex,sample_entropy\na,idf,xyz,1.0\n"
        with self.assertRaisesRegex(ValueError, "header"):
            analyze(raw, hashlib.sha256(raw).hexdigest())

    def test_nonfinite_entropy_rejected(self):
        raw = b"path,category,header64_hex,sample_entropy\na,idf,00,nan\n"
        with self.assertRaisesRegex(ValueError, "entropy"):
            analyze(raw, hashlib.sha256(raw).hexdigest())

    def test_no_idf_rejected(self):
        raw = b"path,category,header64_hex,sample_entropy\na,other,00,1.0\n"
        with self.assertRaisesRegex(ValueError, "No IDF"):
            analyze(raw, hashlib.sha256(raw).hexdigest())

    def test_same_input_output_is_rejected(self):
        raw, digest = fixture()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.csv"
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "overwrite"):
                run(path, digest, path)
            self.assertEqual(path.read_bytes(), raw)

    def test_run_emits_only_aggregate_json(self):
        raw, digest = fixture()
        with tempfile.TemporaryDirectory() as folder:
            private = Path(folder) / "private.csv"
            public = Path(folder) / "public.json"
            private.write_bytes(raw)
            report = run(private, digest, public)
            self.assertEqual(json.loads(public.read_text()), report)
            self.assertNotIn("PRIVATE_", public.read_text())


if __name__ == "__main__":
    unittest.main()
