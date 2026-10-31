"""Synthetic-only tests; no proprietary files, executables or IDF data."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from idf_signature_evidence import analyze_csv, write_public


class SignatureEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.csv = self.root / "private.csv"

    def write_rows(self, rows):
        with self.csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=("path", "category", "header64_hex", "sample_entropy"))
            writer.writeheader()
            writer.writerows(rows)
        return hashlib.sha256(self.csv.read_bytes()).hexdigest()

    def test_magic_and_zlib_and_embedded(self):
        sha = self.write_rows([
            dict(path="PRIVATE/A.IDF", category="idf", header64_hex=(b"PK\x03\x04" + b"A" * 60).hex(), sample_entropy="2.1"),
            dict(path="PRIVATE/B.IDF", category="idf", header64_hex=(b"\x78\x9c" + b"B" * 62).hex(), sample_entropy="7.95"),
            dict(path="PRIVATE/C.IDF", category="idf", header64_hex=(b"X" * 12 + b"\x1f\x8b\x08" + b"Y" * 49).hex(), sample_entropy="1.0"),
            dict(path="PRIVATE/D.IDF", category="idf", header64_hex="00", sample_entropy="0"),
            dict(path="IGNORE.txt", category="text", header64_hex="zz", sample_entropy="bad"),
        ])
        result = analyze_csv(self.csv, sha)
        self.assertEqual(result["idf_header_records"], 4)
        self.assertEqual(result["csv_rows"], 5)
        self.assertEqual(result["known_magic_at_offset_zero"], {"zip": 1})
        self.assertEqual(result["known_magic_at_nonzero_offset"], {"gzip": 1})
        self.assertEqual(result["zlib_header_compatible_at_zero"], 1)
        self.assertEqual(result["sample_entropy_ge_7_9"], 1)
        self.assertEqual(result["shorter_than_64_byte_headers"], 1)
        self.assertFalse(result["idf_decoder_proven"])
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertNotIn("header64_hex", json.dumps(result))

    def test_wrong_hash_fails_closed(self):
        self.write_rows([dict(path="x.idf", category="idf", header64_hex="00", sample_entropy="0")])
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            analyze_csv(self.csv, "0" * 64)

    def test_duplicate_private_paths_rejected_casefold(self):
        sha = self.write_rows([dict(path=p, category="idf", header64_hex="00", sample_entropy="0") for p in ("A.IDF", "a.idf")])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            analyze_csv(self.csv, sha)

    def test_malformed_hex_rejected(self):
        for bad in ("xyz", "123", "00" * 65):
            sha = self.write_rows([dict(path="A.IDF", category="idf", header64_hex=bad, sample_entropy="0")])
            with self.assertRaisesRegex(ValueError, "header hex"):
                analyze_csv(self.csv, sha)

    def test_invalid_entropy_rejected(self):
        for bad in ("NaN", "9", "-1", "bad"):
            sha = self.write_rows([dict(path="A.IDF", category="idf", header64_hex="00", sample_entropy=bad)])
            with self.assertRaisesRegex(ValueError, "entropy"):
                analyze_csv(self.csv, sha)

    def test_no_idf_rows_rejected(self):
        sha = self.write_rows([dict(path="X.TXT", category="text", header64_hex="00", sample_entropy="0")])
        with self.assertRaisesRegex(ValueError, "No IDF"):
            analyze_csv(self.csv, sha)

    def test_output_redacts_and_does_not_overwrite_private_csv(self):
        sha = self.write_rows([dict(path="SECRET/ONE.IDF", category="idf", header64_hex="504b0304", sample_entropy="1")])
        result = analyze_csv(self.csv, sha)
        dest = self.root / "public.json"
        write_public(result, self.csv, dest)
        report = dest.read_text()
        self.assertIn('"zip": 1', report)
        self.assertNotIn("SECRET", report)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            write_public(result, self.csv, self.csv)

    def test_input_symlink_rejected_when_available(self):
        sha = self.write_rows([dict(path="A.IDF", category="idf", header64_hex="00", sample_entropy="0")])
        link = self.root / "link.csv"
        try:
            link.symlink_to(self.csv)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        with self.assertRaisesRegex(ValueError, "non-linked"):
            analyze_csv(link, sha)


if __name__ == "__main__":
    unittest.main()
