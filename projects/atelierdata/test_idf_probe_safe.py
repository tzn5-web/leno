"""Synthetic-only regression tests; no proprietary data or original binaries."""
import hashlib
import io
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from idf_probe_safe import probe_idf, MAX_FILE_BYTES


class ProbeSafetyTests(unittest.TestCase):
    def test_directory_case_and_full_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = b"synthetic-not-a-real-IDF" * 5000
            (root / "demo.idf").write_bytes(data)
            (root / "ignored.txt").write_bytes(b"x")
            result = probe_idf(root)
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["samples"][0]["sha256_computed"], hashlib.sha256(data).hexdigest())
            self.assertEqual(result["samples"][0]["sampled_bytes"], 65536)
            self.assertFalse(result["idf_decoder_proven"])

    def test_single_idf_file_digest_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.IDF"
            data = b"single-synthetic-idf" * 100
            path.write_bytes(data)
            result = probe_idf(path)
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["total_idf_bytes_hashed"], len(data))
            self.assertEqual(result["samples"][0]["name"], "one.IDF")
            self.assertEqual(result["samples"][0]["sha256_computed"],
                             hashlib.sha256(data).hexdigest())
            self.assertFalse(result["idf_decoder_proven"])

    def test_single_idf_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.idf"
            path.touch()
            result = probe_idf(path)
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["samples"][0]["sample_entropy"], 0.0)

    def test_single_file_wrong_extension_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "original.exe"
            path.write_bytes(b"not-executed")
            with self.assertRaisesRegex(ValueError, "directory or ZIP"):
                probe_idf(path)

    def test_zip_stream_and_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "sample.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("folder/SAMPLE.IdF", b"abc" * 100)
                z.writestr("readme.txt", b"ignore")
            result = probe_idf(archive)
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["samples"][0]["bytes"], 300)

    def test_zip_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "sample.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("../outside.IDF", b"x")
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                probe_idf(archive)

    def test_duplicate_casefold_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "sample.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("X.IDF", b"a")
                z.writestr("x.idf", b"b")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                probe_idf(archive)

    def test_zip_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "sample.zip"
            link = zipfile.ZipInfo("link.idf")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr(link, b"elsewhere")
            with self.assertRaisesRegex(ValueError, "symlink"):
                probe_idf(archive)

    def test_zip_oversize_metadata_rejected_without_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "sample.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("x.IDF", b"x")
            with zipfile.ZipFile(archive) as z:
                member = z.infolist()[0]
                member.file_size = MAX_FILE_BYTES + 1
                # Directly exercise declared-size guard with a synthetic stream.
                from idf_probe_safe import _read_digest
                with self.assertRaisesRegex(ValueError, "size limit"):
                    _read_digest(io.BytesIO(b"x"), member.file_size)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink not available")
    def test_input_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real = root / "real"
            real.mkdir()
            link = root / "link"
            try:
                link.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks require elevated Windows privilege")
            with self.assertRaisesRegex(ValueError, "Symbolic"):
                probe_idf(link)

    def test_synthetic_fixed_stride_is_evidence_not_decoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = (b"ABCDEFGH" + b"0123456789abc") * 24
            (root / "stride.IDF").write_bytes(payload)
            report = probe_idf(root)
            entry = report["samples"][0]
            self.assertGreaterEqual(entry["motif_run_count"], 20)
            self.assertEqual(entry["motif_stride_bytes"], 21)
            self.assertFalse(entry["decoded"])
            self.assertFalse(report["idf_decoder_proven"])

    def test_empty_idf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "EMPTY.IDF").write_bytes(b"")
            result = probe_idf(root)
            self.assertEqual(result["samples"][0]["sample_entropy"], 0.0)
            self.assertEqual(result["samples"][0]["sha256_computed"], hashlib.sha256(b"").hexdigest())


if __name__ == "__main__":
    unittest.main()
