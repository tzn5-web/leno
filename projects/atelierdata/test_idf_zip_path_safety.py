"""Regression checks for ZIP path canonicalization in the read-only IDF probe."""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from idf_probe_safe import _entry_name, probe_idf


class ZipPathSafetyTests(unittest.TestCase):
    def test_ambiguous_components_rejected(self):
        for name in ("a//b.idf", "a/./b.idf", "a/../b.idf", "/a.idf", "C:/a.idf"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                _entry_name(name)

    def test_normal_nested_path_accepted(self):
        self.assertEqual(_entry_name("nested/valid.IDF").as_posix(), "nested/valid.IDF")

    def test_directory_file_alias_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "test.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("A/", b"")
                z.writestr("a", b"")
            with self.assertRaisesRegex(ValueError, "Duplicate ZIP member"):
                probe_idf(archive)

    def test_double_separator_rejected_before_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "test.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("nested//x.idf", b"synthetic")
            with self.assertRaisesRegex(ValueError, "Unsafe ZIP entry"):
                probe_idf(archive)


if __name__ == "__main__":
    unittest.main()
