"""Synthetic-only integrity gate regression tests."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from idf_sample_integrity import verify_local_sample


class IntegrityTests(unittest.TestCase):
    def test_verified_synthetic_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.idf"
            payload = b"synthetic-only-not-proprietary" * 100
            path.write_bytes(payload)
            report = verify_local_sample(path, hashlib.sha256(payload).hexdigest())
            self.assertTrue(report["sha256_matches_expected"])
            self.assertFalse(report["source_executed"])
            self.assertFalse(report["idf_decoder_proven"])
            self.assertNotIn(str(path), str(report))
            self.assertNotIn(payload.decode(), str(report))

    def test_mismatch_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.idf"
            path.write_bytes(b"not original")
            report = verify_local_sample(path, "0" * 64)
            self.assertFalse(report["sha256_matches_expected"])

    def test_size_limit_and_invalid_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.idf"
            path.write_bytes(b"12345")
            with self.assertRaises(ValueError):
                verify_local_sample(path, "0" * 64, max_bytes=4)
            with self.assertRaises(ValueError):
                verify_local_sample(path, "z" * 64)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "target"
            link = Path(folder) / "link"
            target.write_bytes(b"test")
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable on this runner")
            with self.assertRaises(ValueError):
                verify_local_sample(link, hashlib.sha256(b"test").hexdigest())


if __name__ == "__main__":
    unittest.main()
