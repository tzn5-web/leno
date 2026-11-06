"""Regression tests for final pathname metadata integrity checks (synthetic files)."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from idf_sample_integrity import verify_local_sample


class FinalPathMetadataTests(unittest.TestCase):
    def test_unchanged_file_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.bin"
            payload = b"atelierdata synthetic sample"
            path.write_bytes(payload)
            result = verify_local_sample(path, hashlib.sha256(payload).hexdigest())
            self.assertTrue(result["sha256_matches_expected"])

    def test_same_inode_metadata_change_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.bin"
            payload = b"synthetic-only"
            path.write_bytes(payload)
            real_lstat = Path.lstat
            calls = [0]

            def changed_final_stat(p):
                result = real_lstat(p)
                calls[0] += 1
                if calls[0] == 1:
                    return result
                # Same inode, altered metadata: a pathname identity check alone misses it.
                class Altered:
                    def __init__(self, original):
                        self.__dict__.update((name, getattr(original, name)) for name in (
                            "st_mode", "st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"))
                        self.st_mtime_ns += 1
                return Altered(result)

            with patch.object(Path, "lstat", changed_final_stat):
                with self.assertRaisesRegex(ValueError, "metadata changed"):
                    verify_local_sample(path, hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    unittest.main()
