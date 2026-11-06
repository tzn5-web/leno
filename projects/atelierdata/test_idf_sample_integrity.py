"""Synthetic-only integrity gate regression tests."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import os
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


    def test_path_replacement_before_open_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.idf"
            replacement = Path(folder) / "replacement.idf"
            path.write_bytes(b"original")
            replacement.write_bytes(b"replacement")
            real_open = os.open

            def replace_then_open(target, flags, *args, **kwargs):
                path.unlink()
                replacement.rename(path)
                return real_open(target, flags, *args, **kwargs)

            with patch("idf_sample_integrity.os.open", side_effect=replace_then_open):
                with self.assertRaises(ValueError):
                    verify_local_sample(path, hashlib.sha256(b"original").hexdigest())

    def test_same_inode_mutation_before_open_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.idf"
            original = b"first payload"
            path.write_bytes(original)
            real_open = os.open

            def mutate_then_open(target, flags, *args, **kwargs):
                # Same inode and size: inode-only checks must not pass.
                path.write_bytes(b"other payload")
                os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 2_000_000_000))
                return real_open(target, flags, *args, **kwargs)

            with patch("idf_sample_integrity.os.open", side_effect=mutate_then_open):
                with self.assertRaisesRegex(ValueError, "metadata changed before opening"):
                    verify_local_sample(path, hashlib.sha256(original).hexdigest())

    def test_path_replacement_during_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.idf"
            replacement = Path(folder) / "replacement.idf"
            path.write_bytes(b"original")
            replacement.write_bytes(b"replacement")
            real_fstat = os.fstat
            calls = [0]

            def swap_on_second_fstat(fd):
                calls[0] += 1
                if calls[0] == 2:
                    try:
                        path.unlink()
                        replacement.rename(path)
                    except PermissionError:
                        raise unittest.SkipTest("Windows locks open files; replacement cannot be simulated")
                return real_fstat(fd)

            with patch("idf_sample_integrity.os.fstat", side_effect=swap_on_second_fstat):
                with self.assertRaises(ValueError):
                    verify_local_sample(path, hashlib.sha256(b"original").hexdigest())


if __name__ == "__main__":
    unittest.main()
