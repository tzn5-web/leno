"""Synthetic-only regression tests for IDF probe resource and safety policy."""
from __future__ import annotations

import itertools
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from idf_probe_safe import (
    MAX_DIRECTORY_ENTRIES,
    MAX_FILE_BYTES,
    probe_idf,
)


class ProbePolicyTests(unittest.TestCase):
    def test_blocked_part_0016_rejected_before_archive_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked = Path(tmp) / "autodata_part_0016.zip"
            blocked.write_bytes(b"synthetic-placeholder-not-an-archive")
            with patch("idf_probe_safe.zipfile.ZipFile") as open_archive:
                with self.assertRaisesRegex(ValueError, "Blocked package part_0016"):
                    probe_idf(blocked)
                open_archive.assert_not_called()

    def test_blocked_part_0016_case_insensitive_even_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked = Path(tmp) / "AUTODATA_PART_0016.ZIP"
            with self.assertRaisesRegex(ValueError, "Blocked package part_0016"):
                probe_idf(blocked)

    def test_non_idf_directory_flood_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            non_idf = root / "synthetic.txt"
            entries = itertools.repeat(non_idf, MAX_DIRECTORY_ENTRIES + 1)
            with patch.object(Path, "rglob", return_value=entries):
                with self.assertRaisesRegex(ValueError, "directory entry limit"):
                    probe_idf(root)

    def test_oversize_directory_idf_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "synthetic.idf"
            # Sparse synthetic file; does not allocate or read 256 MiB.
            with path.open("wb") as stream:
                stream.truncate(MAX_FILE_BYTES + 1)
            with patch.object(Path, "open", wraps=Path.open) as opened:
                with self.assertRaisesRegex(ValueError, "IDF file exceeds size limit"):
                    probe_idf(root)
                # The file is not opened for hashing after the size check.
                opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
