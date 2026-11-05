"""Synthetic ZIP member-type regression; never reads private Autodata files."""
import hashlib
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from idf_stride_evidence import first_verified_chunk


class ZipMemberTypeTests(unittest.TestCase):
    def test_symlink_member_refused_even_with_matching_digest(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            payload = b"synthetic-link-target"
            archive_path = directory / "autodata_part_0001.zip"
            info = zipfile.ZipInfo("COMMON/SGOPS.IDF")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(info, payload)
            manifest = {"files": [{
                "path": "COMMON/SGOPS.IDF",
                "chunks": [{"package": archive_path.name,
                            "entry": info.filename,
                            "bytes": len(payload),
                            "sha256": hashlib.sha256(payload).hexdigest()}]
            }]}
            with self.assertRaisesRegex(ValueError, "Symlink ZIP member refused"):
                first_verified_chunk(manifest, directory, "SGOPS.IDF")

    def test_regular_member_still_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            payload = b"synthetic-ordinary-idf-data"
            archive_path = directory / "autodata_part_0001.zip"
            info = zipfile.ZipInfo("COMMON/SGOPS.IDF")
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(info, payload)
            manifest = {"files": [{
                "path": "COMMON/SGOPS.IDF",
                "chunks": [{"package": archive_path.name,
                            "entry": info.filename,
                            "bytes": len(payload),
                            "sha256": hashlib.sha256(payload).hexdigest()}]
            }]}
            sample, size = first_verified_chunk(manifest, directory, "SGOPS.IDF")
            self.assertEqual((sample, size), (payload, len(payload)))


if __name__ == "__main__":
    unittest.main()
