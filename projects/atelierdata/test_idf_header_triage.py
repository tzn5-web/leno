"""Synthetic-only tests for IDF metadata triage; no proprietary fixtures."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from idf_header_triage import inspect


class TestIdfHeaderTriage(unittest.TestCase):
    def test_verified_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.idf"
            data = bytes(range(256)) * 4
            path.write_bytes(data)
            result = inspect(path, hashlib.sha256(data).hexdigest())
            self.assertTrue(result["sha256_verified"])
            self.assertEqual(result["size_bytes"], len(data))
            self.assertEqual(result["sample_entropy_bits_per_byte"], 8.0)
            self.assertFalse(result["format_identified"])
            self.assertFalse(result["decoder_verified"])

    def test_wrong_digest_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.idf"
            path.write_bytes(b"sample")
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                inspect(path, "0" * 64)

    def test_invalid_sample_size_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.idf"
            path.write_bytes(b"")
            with self.assertRaises(ValueError):
                inspect(path, hashlib.sha256(b"").hexdigest(), 65537)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.idf"
            path.write_bytes(b"sample")
            link = Path(directory) / "alias.idf"
            try:
                link.symlink_to(path)
            except OSError:
                self.skipTest("symlink unavailable")
            with self.assertRaises(ValueError):
                inspect(link, hashlib.sha256(b"sample").hexdigest())


if __name__ == "__main__":
    unittest.main()
